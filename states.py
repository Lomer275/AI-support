from enum import Enum


class SessionState(str, Enum):
    WAITING_INN = "waiting_inn"
    WAITING_PHONE = "waiting_phone"
    AUTHORIZED = "authorized"
