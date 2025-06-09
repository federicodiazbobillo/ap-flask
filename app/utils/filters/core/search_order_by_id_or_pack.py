def filtro_por_id_o_pack(valor):
    if not valor:
        return None

    return {
        "where": "(id = %s OR pack_id = %s)",
        "params": [valor, valor]
    }
