"""Document validator service (S04/T20).

Three-level pipeline:
  1. Format filter  — skip non-visual files (.docx, .xlsx, etc.)
  2. GPT-4o-mini Vision — classify doc type and check readability
  3. Checklist update — recalculate cases.checklist_completion

Called from webhook_server.py when new files appear in a Bitrix deal folder.
"""
import base64
import io
import logging
import os
from datetime import datetime, timezone
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

# ── Checklist items (fixed denominator for completion %) ──────────────────────

CHECKLIST_ITEMS: dict[str, str] = {
    "passport":              "Паспорт РФ (все страницы без обложки)",
    "foreign_passport":      "Заграничный паспорт",
    "snils":                 "СНИЛС",
    "inn_certificate":       "Свидетельство ИНН",
    "birth_certificate":     "Свидетельство о рождении",
    "marriage_certificate":  "Свидетельство о браке / расторжении брака (ЗАГС)",
    "spouse_passport":       "Копия паспорта супруга/супруги",
    "death_certificate":     "Свидетельство о смерти супруга",
    "children_certificates": "Свидетельства о рождении детей",
    "dependents_docs":       "Документы об иждивенцах",
    "employment_record":     "Трудовая книжка",
    "income_2ndfl":          "Справка 2-НДФЛ",
    "pension_certificate":   "Пенсионное удостоверение",
    "gosuslugi":             "Госуслуги (скриншот личного кабинета)",
    "bank_statements":       "Выписки по банковским счетам за 3 года",
    "gibdd_reference":       "Справка ГИБДД об имуществе",
    "property_docs":         "Документы о праве собственности",
    "debt_docs":             "Кредитные договоры / справки о задолженности",
}

CHECKLIST_TOTAL = len(CHECKLIST_ITEMS)  # 18

# ── Format support ────────────────────────────────────────────────────────────

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}
_PDF_EXT = ".pdf"
_MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB — OpenAI Vision limit
_MAX_IMAGE_PX = 1500                 # resize long side to this

# ── Vision prompt ─────────────────────────────────────────────────────────────

_CHECKLIST_LINES = "\n".join(f"- {k}: {v}" for k, v in CHECKLIST_ITEMS.items())

VISION_PROMPT = f"""Ты проверяешь документ клиента для процедуры банкротства физического лица.

Возможные типы документов:
{_CHECKLIST_LINES}
- unknown: не удалось определить тип

Определи:
1. Тип документа из списка выше (поле doc_type — используй ключ, например "passport")
2. Документ читаем и пригоден для суда? Текст/данные различимы? (readable: true/false)
3. Если нечитаем — укажи причину по-русски (reason), иначе null

Ответь строго валидным JSON без пояснений:
{{"doc_type": "...", "readable": true, "reason": null}}"""


# ── DocumentValidator ─────────────────────────────────────────────────────────

class DocumentValidator:
    """Validates Bitrix deal documents via GPT-4o-mini Vision."""

    def __init__(
        self,
        http_session: aiohttp.ClientSession,
        openai_api_key: str,
        cases_url: str,
        cases_key: str,
        bitrix_base: str,
        model: str = "gpt-4o-mini",
        openai_proxy: str | None = None,
    ) -> None:
        self._session = http_session
        self._api_key = openai_api_key
        self._cases_url = cases_url
        self._cases_key = cases_key
        self._bitrix_base = bitrix_base
        self._model = model
        self._proxy = openai_proxy

    # ── Public entry point ────────────────────────────────────────────────────

    async def process_deal_files(self, inn: str, deal_id: str) -> None:
        """Fetch new files from Bitrix deal folder, validate up to 10."""
        if not inn:
            return

        try:
            folder_id = await self._get_root_folder_id(deal_id)
            if not folder_id:
                logger.debug("[VALIDATOR] deal_id=%s: no disk folder, skipping", deal_id)
                return

            files = await self._list_folder_files(folder_id)
            if not files:
                return

            known_ids = await self._get_known_file_ids(inn)
            new_files = [f for f in files if str(f["ID"]) not in known_ids]

            if not new_files:
                logger.debug("[VALIDATOR] deal_id=%s: no new files", deal_id)
                return

            logger.info("[VALIDATOR] deal_id=%s: %d new file(s)", deal_id, len(new_files))

            # Insert all new files as pending first
            await self._insert_pending_files(inn, new_files)

            # Validate up to 10
            for file in new_files[:10]:
                await self._validate_one(inn, file)

            # Recalculate checklist completion
            await self._update_checklist_completion(inn)

        except Exception:
            logger.exception("[VALIDATOR] Unexpected error for deal_id=%s inn=%s", deal_id, inn)

    # ── Bitrix Disk API ───────────────────────────────────────────────────────

    async def _get_root_folder_id(self, deal_id: str) -> str | None:
        """Get client folder ID from shared disk by matching folder name from folder_url.

        folder_url format: https://bitrix.../docs/shared/path/<encoded_name>
        Client folders live in the root of shared disk (storage_id=11, root_folder_id=19).
        We search by folder name using disk.folder.getchildren with filter.
        """
        # First get folder_url from cases table
        try:
            async with self._session.get(
                f"{self._cases_url}/rest/v1/cases",
                headers=self._supabase_headers(""),
                params={"deal_id": f"eq.{deal_id}", "select": "folder_url"},
            ) as resp:
                rows = await resp.json(content_type=None)
            if not rows or not rows[0].get("folder_url"):
                return None
            folder_url = rows[0]["folder_url"]
        except Exception:
            logger.warning("[VALIDATOR] failed to get folder_url for deal_id=%s", deal_id)
            return None

        # Extract folder name from URL: .../docs/shared/path/<name>
        import urllib.parse
        try:
            path = urllib.parse.urlparse(folder_url).path  # /docs/shared/path/Аксенов...
            folder_name = urllib.parse.unquote(path.split("/path/")[-1])
        except Exception:
            logger.warning("[VALIDATOR] cannot parse folder_url=%s", folder_url)
            return None

        if not folder_name:
            return None

        # Search in shared disk root (ID=19) by name
        try:
            async with self._session.post(
                f"{self._bitrix_base}/disk.folder.getchildren",
                data={"id": "19", "filter[NAME]": folder_name, "filter[TYPE]": "folder"},
            ) as resp:
                data = await resp.json(content_type=None)
            items = data.get("result", [])
            if items:
                folder_id = str(items[0]["ID"])
                logger.info("[VALIDATOR] deal_id=%s folder '%s' → id=%s", deal_id, folder_name, folder_id)
                return folder_id
            logger.info("[VALIDATOR] deal_id=%s folder '%s' not found in shared disk", deal_id, folder_name)
            return None
        except Exception:
            logger.warning("[VALIDATOR] disk.folder.getchildren search failed for deal_id=%s", deal_id)
            return None

    async def _list_folder_files(self, folder_id: str) -> list[dict]:
        """List files in root folder and one level of subfolders.

        Client folders contain subfolders (e.g. "Неразобранное", "Паспорт", etc.)
        with files inside — so we scan root + all immediate subfolders.
        """
        all_files: list[dict] = []
        try:
            async with self._session.post(
                f"{self._bitrix_base}/disk.folder.getchildren",
                data={"id": folder_id},
            ) as resp:
                data = await resp.json(content_type=None)
            items = data.get("result", [])
        except Exception:
            logger.warning("[VALIDATOR] disk.folder.getchildren failed for folder_id=%s", folder_id)
            return []

        for item in items:
            if item.get("TYPE") == "file":
                all_files.append(item)
            elif item.get("TYPE") == "folder":
                # One level deep
                try:
                    async with self._session.post(
                        f"{self._bitrix_base}/disk.folder.getchildren",
                        data={"id": item["ID"], "filter[TYPE]": "file"},
                    ) as resp:
                        sub = await resp.json(content_type=None)
                    all_files.extend(sub.get("result", []))
                except Exception:
                    logger.warning("[VALIDATOR] subfolder scan failed id=%s", item.get("ID"))

        return all_files

    async def _download_file(self, file_info: dict) -> bytes | None:
        """Download file content from Bitrix disk."""
        download_url = file_info.get("DOWNLOAD_URL") or file_info.get("DETAIL_URL")
        if not download_url:
            return None
        try:
            async with self._session.get(download_url) as resp:
                if resp.status != 200:
                    return None
                content = await resp.read()
            if len(content) > _MAX_FILE_BYTES:
                logger.info("[VALIDATOR] file %s too large (%d bytes), skipping Vision",
                            file_info.get("NAME"), len(content))
                return None
            return content
        except Exception:
            logger.warning("[VALIDATOR] download failed for file %s", file_info.get("NAME"))
            return None

    # ── Supabase helpers ──────────────────────────────────────────────────────

    def _supabase_headers(self, prefer: str = "return=minimal") -> dict:
        return {
            "apikey": self._cases_key,
            "Authorization": f"Bearer {self._cases_key}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        }

    async def _get_known_file_ids(self, inn: str) -> set[str]:
        """Return set of bitrix_file_id already in documents table."""
        try:
            async with self._session.get(
                f"{self._cases_url}/rest/v1/documents",
                headers=self._supabase_headers(""),
                params={"inn": f"eq.{inn}", "select": "bitrix_file_id"},
            ) as resp:
                rows = await resp.json(content_type=None)
            return {r["bitrix_file_id"] for r in rows if r.get("bitrix_file_id")}
        except Exception:
            logger.warning("[VALIDATOR] failed to fetch known file ids for inn=%s", inn)
            return set()

    async def _insert_pending_files(self, inn: str, files: list[dict]) -> None:
        """Insert all new files as pending (ignore conflicts)."""
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            {
                "inn": inn,
                "bitrix_file_id": str(f["ID"]),
                "file_name": f.get("NAME", ""),
                "status": "pending",
                "uploaded_at": now,
            }
            for f in files
        ]
        try:
            async with self._session.post(
                f"{self._cases_url}/rest/v1/documents",
                headers={**self._supabase_headers(), "Prefer": "resolution=ignore-duplicates"},
                json=rows,
            ) as resp:
                if resp.status not in (200, 201):
                    text = await resp.text()
                    logger.warning("[VALIDATOR] insert pending failed: %s", text[:200])
        except Exception:
            logger.warning("[VALIDATOR] insert pending exception for inn=%s", inn)

    async def _update_document(self, inn: str, bitrix_file_id: str, update: dict) -> None:
        """Patch a documents row by inn + bitrix_file_id."""
        try:
            async with self._session.patch(
                f"{self._cases_url}/rest/v1/documents",
                headers=self._supabase_headers(),
                params={"inn": f"eq.{inn}", "bitrix_file_id": f"eq.{bitrix_file_id}"},
                json=update,
            ) as resp:
                if resp.status not in (200, 204):
                    text = await resp.text()
                    logger.warning("[VALIDATOR] update doc failed %s: %s", resp.status, text[:100])
        except Exception:
            logger.warning("[VALIDATOR] update doc exception for file_id=%s", bitrix_file_id)

    async def _update_checklist_completion(self, inn: str) -> None:
        """Recalculate and store checklist_completion in cases."""
        try:
            async with self._session.get(
                f"{self._cases_url}/rest/v1/documents",
                headers=self._supabase_headers(""),
                params={"inn": f"eq.{inn}", "select": "doc_type,status"},
            ) as resp:
                rows = await resp.json(content_type=None)

            # Count unique verified doc_types that are in CHECKLIST_ITEMS
            verified_types = {
                r["doc_type"]
                for r in rows
                if r.get("status") == "verified" and r.get("doc_type") in CHECKLIST_ITEMS
            }
            completion = round(len(verified_types) / CHECKLIST_TOTAL, 4)

            async with self._session.patch(
                f"{self._cases_url}/rest/v1/cases",
                headers=self._supabase_headers(),
                params={"inn": f"eq.{inn}"},
                json={"checklist_completion": completion},
            ) as resp:
                if resp.status not in (200, 204):
                    text = await resp.text()
                    logger.warning("[VALIDATOR] update checklist failed: %s", text[:100])
                else:
                    logger.info("[VALIDATOR] inn=%s checklist_completion=%.1f%%",
                                inn, completion * 100)
        except Exception:
            logger.warning("[VALIDATOR] checklist update exception for inn=%s", inn)

    # ── Image preparation ─────────────────────────────────────────────────────

    @staticmethod
    def _to_base64_image(content: bytes, ext: str) -> str | None:
        """Convert file bytes to base64 PNG for Vision API.

        - Images: resize to max 1500px, encode as PNG
        - PDFs: render first page via PyMuPDF, encode as PNG
        Returns base64 string or None if unsupported/error.
        """
        try:
            if ext in _IMAGE_EXTS:
                from PIL import Image
                img = Image.open(io.BytesIO(content)).convert("RGB")
                img.thumbnail((_MAX_IMAGE_PX, _MAX_IMAGE_PX))
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return base64.b64encode(buf.getvalue()).decode()

            if ext == _PDF_EXT:
                import fitz  # PyMuPDF
                doc = fitz.open(stream=content, filetype="pdf")
                if doc.page_count == 0:
                    return None
                page = doc[0]
                # Render at 150 DPI (matrix scale ≈ 150/72)
                mat = fitz.Matrix(150 / 72, 150 / 72)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img_bytes = pix.tobytes("png")
                doc.close()
                # Resize if needed
                from PIL import Image
                img = Image.open(io.BytesIO(img_bytes))
                img.thumbnail((_MAX_IMAGE_PX, _MAX_IMAGE_PX))
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return base64.b64encode(buf.getvalue()).decode()

        except Exception as e:
            logger.warning("[VALIDATOR] image conversion failed (%s): %s", ext, e)

        return None

    # ── Vision call ───────────────────────────────────────────────────────────

    async def _call_vision(self, image_b64: str) -> dict | None:
        """Send image to GPT-4o-mini Vision. Returns parsed JSON or None."""
        import json

        payload = {
            "model": self._model,
            "max_tokens": 150,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_b64}", "detail": "low"},
                        },
                    ],
                }
            ],
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        url = "https://api.openai.com/v1/chat/completions"
        try:
            async with self._session.post(
                url, headers=headers, json=payload, proxy=self._proxy
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.warning("[VALIDATOR] OpenAI error %s: %s", resp.status, text[:200])
                    return None
                data = await resp.json(content_type=None)

            raw = data["choices"][0]["message"]["content"].strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw)
        except Exception as e:
            logger.warning("[VALIDATOR] Vision call failed: %s", e)
            return None

    # ── Single file validation ────────────────────────────────────────────────

    async def _validate_one(self, inn: str, file_info: dict) -> str:
        """Validate one file. Returns final status string."""
        file_id = str(file_info["ID"])
        file_name = file_info.get("NAME", "")
        ext = os.path.splitext(file_name)[1].lower()

        # Level 1: format filter
        if ext not in _IMAGE_EXTS and ext != _PDF_EXT:
            logger.info("[VALIDATOR] %s → not_applicable (unsupported format %s)", file_name, ext)
            await self._update_document(inn, file_id, {"status": "not_applicable"})
            return "not_applicable"

        # Level 2: download + Vision
        content = await self._download_file(file_info)
        if content is None:
            # Leave as pending — transient download error
            logger.warning("[VALIDATOR] %s → pending (download failed)", file_name)
            return "pending"

        image_b64 = self._to_base64_image(content, ext)
        if image_b64 is None:
            await self._update_document(inn, file_id, {
                "status": "rejected",
                "rejection_reason": "Не удалось прочитать файл",
            })
            return "rejected"

        result = await self._call_vision(image_b64)
        if result is None:
            # Leave as pending — transient OpenAI error
            logger.warning("[VALIDATOR] %s → pending (Vision unavailable)", file_name)
            return "pending"

        doc_type = result.get("doc_type", "unknown")
        readable = result.get("readable", True)
        reason = result.get("reason")

        now = datetime.now(timezone.utc).isoformat()

        if not readable:
            status = "rejected"
            rejection_reason = reason or "Документ нечитаем"
            logger.info("[VALIDATOR] %s → rejected (%s)", file_name, rejection_reason)
            await self._update_document(inn, file_id, {
                "status": status,
                "doc_type": doc_type,
                "rejection_reason": rejection_reason,
            })
        else:
            status = "verified"
            logger.info("[VALIDATOR] %s → verified (doc_type=%s)", file_name, doc_type)
            await self._update_document(inn, file_id, {
                "status": status,
                "doc_type": doc_type,
                "rejection_reason": None,
                "verified_at": now,
            })

        return status
