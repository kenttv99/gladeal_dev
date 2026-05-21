from enum import Enum

class ORDERS_STATES(Enum):

    """
    AWAITING_PERFORMER - сделка ожидает исполнителя (З1)
    AWAITING_PAYMENT - сделка ожидает оплаты (З2/И2)
    AWAITING_PERFORMER_CONFIRMATION - сделка ожидает подтверждения исполнителем (З3/И3)
    AWAITING_CLIENT_CONFIRMATION - сделка ожидает подтверждения заказчиком (З4/И4)
    AWAITING_CONFLICT - отказ заказчика требует подтверждения отказа исполнителем (З5/И5)
    OPEN_CONFLICT - открыт спор (З6/И6)

    """

    AWAITING_PERFORMER = 'AWAITING_PERFORMER'
    AWAITING_PAYMENT  = 'AWAITING_PAYMENT'
    AWAITING_PERFORMER_CONFIRMATION = 'AWAITING_PERFORMER_CONFIRMATION'
    AWAITING_CLIENT_CONFIRMATION  = 'AWAITING_CLIENT_CONFIRMATION'
    AWAITING_CONFLICT = 'AWAITING_CONFLICT'
    OPEN_CONFLICT = 'OPEN_CONFLICT'