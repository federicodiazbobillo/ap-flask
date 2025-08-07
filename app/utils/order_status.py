def estado_logico(order_status, shipment_status, shipment_substatus):
    if order_status == 'paid' and shipment_status == 'delivered' and not shipment_substatus:
        return '✅ Entregado y cobrado'
    if order_status == 'cancelled' and shipment_status == 'cancelled' and not shipment_substatus:
        return '✖ Cancelada sin enviar'

    return f"❓ Estado no identificado: order_status={order_status}, shipment_status={shipment_status}, substatus={shipment_substatus}"
