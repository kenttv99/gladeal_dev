from enum import Enum


class OrderStates(Enum):
    """
    AWAITING_PERFORMER - сделка ожидает исполнителя (З1)
    AWAITING_PAYMENT - сделка ожидает оплаты (З2/И2)
    AWAITING_PERFORMER_CONFIRMATION - сделка ожидает подтверждения исполнителем (З3/И3)
    AWAITING_CLIENT_CONFIRMATION - сделка ожидает подтверждения заказчиком (З4/И4)
    AWAITING_PERFORMER_PAYOUT - сделка ожидает подтверждения выплаты заказчиком
    AWAITING_CONFLICT - отказ заказчика требует подтверждения отказа исполнителем (З5/И5)
    OPEN_CONFLICT - открыт спор (З6/И6)
    SUCCESSFUL_COMPLETION - успешное завершение (З7/И7)
    UNSUCCESSFUL_COMPLETION - неуспешное завершение (З8/И8)
    CANCLED_BY_EXPIRE_TIME_TO_CLIENT - отменена с возвратом средств заказчику(З9/И9)
    CONFIRM_BY_EXPIRE_TIME_TO_PERFORMER - подтверждена с переводом средств исполнителю(З10/И10)
    CLOSED_BY_ARBITER_TO_CLIENT - закрыта арбитром в пользу клиента (З11/И11)
    CLOSED_BY_ARBITER_TO_PERFORMER - закрыта арбитром в пользу исполнителя (З12/И12)
    """

    AWAITING_PERFORMER = "awaiting_performer"
    AWAITING_PAYMENT = "awaiting_payment"
    AWAITING_PERFORMER_CONFIRMATION = "awaiting_performer_confirmation"
    AWAITING_CLIENT_CONFIRMATION = "awaiting_client_confirmation"
    AWAITING_PERFORMER_PAYOUT = "awaiting_performer_payout"
    AWAITING_CONFLICT = "awaiting_conflict"
    OPEN_CONFLICT = "open_conflict"
    SUCCESSFUL_COMPLETION = "successful_completion"
    UNSUCCESSFUL_COMPLETION = "unsuccessful_completion"
    CANCLED_BY_EXPIRE_TIME = "cancled_by_expire_time_to_client"
    CONFIRM_BY_EXPIRE_TIME_TO_PERFORMER = "confirm_by_expire_time_to_performer"
    CLOSED_BY_ARBITER_TO_CLIENT = "closed_by_arbiter_to_client"
    CLOSED_BY_ARBITER_TO_PERFORMER = "closed_by_arbiter_to_performer"



class UserRoles(Enum):
    PERFORMER = "performer"
    CLIENT = "client"


class AdminRoles(Enum):
    SUPERUSER = "superuser"
    ADMIN = "admin"
    SUPPORT = "support"


class VerificationScopes(Enum):
    REGISTER = "register"
    LOGIN = "login"
    RESET_PHONE_NUMBER = "reset_phone_number"


class VerificationMethods(Enum):
    SMS = "sms"
    CALL = "call"


class OrderPaymentStates(Enum):
    REGISTERED = "registered"
    AUTHORIZED = "authorized"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELED = "canceled"
    EXPIRED = "expired"


###
# Набросок для уведомлений
###

class NotificationTypes(Enum):
    ORDER = "order"
    REVIEW = "review"
    PROMOTION = "promotion"
    NEWS = "news"


class NotificationStatuses(Enum):
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"
    FAILED = "failed"
