"""Gera uma planilha de teste com a aba BASE (dados ficticios) para preview.

Inclui as colunas novas (Email, Link de Cobranca) para exercitar o sync completo.
Uso: python scripts/gerar_base_teste.py
"""
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "base_teste.xlsx"
OUT.parent.mkdir(parents=True, exist_ok=True)

linhas = [
    {
        "UF": "SP", "Cd.Cliente": "12.345.678/0001-90", "Cliente": "Padaria Aurora LTDA",
        "Email": "financeiro@aurora.com.br", "Título": "TIT-001", "Doc.Fiscal": "NF-1001",
        "Vl.Título": 1500.00, "Juros": 45.00, "Multa": 30.00, "Total Atualizado": 1575.00,
        "Emissão": "2026-04-10", "Vencimento": "2026-05-10", "Prog.Pagto": "", "Ano": 2026,
        "Mês": 5, "OBS": "", "Dias de Atraso": 47,
        "Link de Cobrança": "https://pag.exemplo.com/aurora-001",
    },
    {
        "UF": "MG", "Cd.Cliente": "98.765.432/0001-10", "Cliente": "Mercado Sao Jorge ME",
        "Email": "", "Título": "TIT-002", "Doc.Fiscal": "NF-1002",
        "Vl.Título": 800.00, "Juros": 12.00, "Multa": 16.00, "Total Atualizado": 828.00,
        "Emissão": "2026-05-01", "Vencimento": "2026-06-01", "Prog.Pagto": "", "Ano": 2026,
        "Mês": 6, "OBS": "Sem e-mail cadastrado", "Dias de Atraso": 25,
        "Link de Cobrança": "",
    },
    {
        "UF": "RJ", "Cd.Cliente": "11.222.333/0001-44", "Cliente": "Auto Pecas Veloz LTDA",
        "Email": "contato@veloz.com.br", "Título": "TIT-003", "Doc.Fiscal": "NF-1003",
        "Vl.Título": 3200.00, "Juros": 0.00, "Multa": 0.00, "Total Atualizado": 3200.00,
        "Emissão": "2026-06-05", "Vencimento": "2026-06-20", "Prog.Pagto": "", "Ano": 2026,
        "Mês": 6, "OBS": "", "Dias de Atraso": 6,
        "Link de Cobrança": "https://pag.exemplo.com/veloz-003",
    },
    {
        "UF": "SP", "Cd.Cliente": "12.345.678/0001-90", "Cliente": "Padaria Aurora LTDA",
        "Email": "financeiro@aurora.com.br", "Título": "TIT-004", "Doc.Fiscal": "NF-1004",
        "Vl.Título": 450.00, "Juros": 9.00, "Multa": 9.00, "Total Atualizado": 468.00,
        "Emissão": "2026-05-15", "Vencimento": "2026-06-15", "Prog.Pagto": "", "Ano": 2026,
        "Mês": 6, "OBS": "", "Dias de Atraso": 11,
        "Link de Cobrança": "",
    },
    {
        "UF": "PR", "Cd.Cliente": "55.666.777/0001-88", "Cliente": "Farmacia Bem Estar LTDA",
        "Email": "adm@bemestar.com.br", "Título": "TIT-005", "Doc.Fiscal": "NF-1005",
        "Vl.Título": 2750.50, "Juros": 82.51, "Multa": 55.01, "Total Atualizado": 2888.02,
        "Emissão": "2026-03-20", "Vencimento": "2026-04-20", "Prog.Pagto": "", "Ano": 2026,
        "Mês": 4, "OBS": "Cliente reincidente", "Dias de Atraso": 67,
        "Link de Cobrança": "https://pag.exemplo.com/bemestar-005",
    },
]

df = pd.DataFrame(linhas)

# Aba INADIMPLENCIA no formato real: cabecalho na LINHA 2 (indice 1),
# CLIENTES na coluna D e STATUS na coluna H. Farmacia fica fora da lista.
vazio = [None, None, None]
inad_linhas = [
    vazio + ["RELATORIO DE INADIMPLENCIA", None, None, None, None, None],   # linha 1: titulo solto
    vazio + ["CLIENTES", "INADIMPLÊNCIA ", "IMPACTO %", "TIPO", "STATUS", "VENCIMENTO"],
    vazio + ["Padaria Aurora LTDA", 2043.00, 0.31, "VENDA", "COBRANÇA", "2026-05-10"],
    vazio + ["Mercado Sao Jorge ME", 828.00, 0.12, "VENDA", "NEGATIVADO", "2026-06-01"],
    vazio + ["Auto Pecas Veloz LTDA", 3200.00, 0.48, "VENDA", "JURIDICO", "2026-06-20"],
]
inad = pd.DataFrame(inad_linhas)

with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
    df.to_excel(writer, sheet_name="BASE", index=False)
    inad.to_excel(writer, sheet_name="INADIMPLÊNCIA", index=False, header=False)
    # Aba extra que deve ser IGNORADA pelo sync
    pd.DataFrame({"ignore": ["esta aba nao deve ser lida"]}).to_excel(
        writer, sheet_name="OUTRA", index=False
    )

print(f"Planilha de teste gerada: {OUT}")
print(f"{len(df)} linhas na BASE + aba INADIMPLENCIA (Aurora=COBRANCA, "
      f"Sao Jorge=NEGATIVADO, Veloz=JURIDICO, Farmacia fora da lista).")
