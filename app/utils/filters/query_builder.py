def construir_consulta(filtros):
    condiciones = []
    parametros = []

    for filtro_func in filtros:
        condicion = filtro_func()
        if condicion:
            condiciones.append(condicion["where"])
            parametros.extend(condicion["params"])

    where_clause = " AND ".join(condiciones) if condiciones else "1=1"
    return where_clause, parametros
