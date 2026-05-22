from enum import Enum

class OrderStates(Enum):

    """
    AWAITING_PERFORMER - сделка ожидает исполнителя (З1)
    AWAITING_PAYMENT - сделка ожидает оплаты (З2/И2)
    AWAITING_PERFORMER_CONFIRMATION - сделка ожидает подтверждения исполнителем (З3/И3)
    AWAITING_CLIENT_CONFIRMATION - сделка ожидает подтверждения заказчиком (З4/И4)
    AWAITING_CONFLICT - отказ заказчика требует подтверждения отказа исполнителем (З5/И5)
    OPEN_CONFLICT - открыт спор (З6/И6)
    SUCCESSFUL_COMPLETION - успешное завершение (З7/И7)
    UNSUCCESSFUL_COMPLETION - неуспешное завершение (З8/И8)
    CLOSED_BY_ARBITER_TO_CLIENT - закрыта арбитром в пользу клиента (З9/И9)
    CLOSED_BY_ARBITER_TO_PERFORMER - закрыта арбитром в пользу исполнителя (З10/И10)
    """

    AWAITING_PERFORMER = 'awaiting_performer'
    AWAITING_PAYMENT  = 'awaiting_payment'
    AWAITING_PERFORMER_CONFIRMATION = 'awaiting_performer_confirmation'
    AWAITING_CLIENT_CONFIRMATION  = 'awaiting_client_confirmation'
    AWAITING_CONFLICT = 'awaiting_conflict'
    OPEN_CONFLICT = 'open_conflict'
    SUCCESSFUL_COMPLETION = 'successful_completion'
    UNSUCCESSFUL_COMPLETION = 'unsuccessful_completion'
    CLOSED_BY_ARBITER_TO_CLIENT = 'closed_by_arbiter_to_client'
    CLOSED_BY_ARBITER_TO_PERFORMER = 'closed_by_arbiter_to_performer'

class UserRoles(Enum):

    PERFORMER = 'performer'
    CLIENT = 'client'
