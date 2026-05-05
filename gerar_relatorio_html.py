"""
Gerador de Relatório de Tráfego Pago — Meta Ads
Uso: python gerar_relatorio_html.py
Requer: dados.csv e analise.txt na mesma pasta
"""

import sys, os, io, json, re
import pandas as pd
from datetime import datetime

# ── Leitura robusta do CSV ─────────────────────────────────────────────────────

def carregar_dados(csv_path):
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            with open(csv_path, "r", encoding=enc) as f:
                raw = f.read()
        except UnicodeDecodeError:
            continue

        lines = raw.splitlines()
        data_lines = [l for l in lines if l.strip()]
        outer_quoted = len(data_lines) > 1 and all(
            l.startswith('"') and l.endswith('"') for l in data_lines
        )
        cleaned = []
        for line in lines:
            if outer_quoted and line.startswith('"') and line.endswith('"'):
                line = line[1:-1]
            line = line.replace('""', chr(0)).replace(chr(0), '"')
            cleaned.append(line)

        clean_content = "\n".join(cleaned)
        for sep in (",", ";", "\t"):
            try:
                df = pd.read_csv(io.StringIO(clean_content), sep=sep)
                df.columns = [c.strip().strip('"') for c in df.columns]
                if len(df.columns) > 3:
                    return df
            except Exception:
                continue

    raise ValueError("Nao foi possivel ler o CSV. Verifique se e um export valido do Meta Ads Manager.")

# ── Helpers de colunas ─────────────────────────────────────────────────────────

def _col(df, *candidatos):
    for c in candidatos:
        if c in df.columns:
            return c
    import unicodedata
    def norm(s):
        return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn").lower()
    for c in df.columns:
        for cand in candidatos:
            if norm(c) == norm(cand):
                return c
    raise KeyError(f"Coluna nao encontrada: {list(candidatos)}\nColunas no CSV: {list(df.columns)}")

def _col_opt(df, *candidatos):
    try:
        return _col(df, *candidatos)
    except KeyError:
        return None

# ── Calculo de metricas ────────────────────────────────────────────────────────

def calcular_metricas(df):
    col_inicio = _col(df, "Inicio dos relatorios", "Início dos relatórios", "Start date")
    col_fim    = _col(df, "Encerramento dos relatorios", "Encerramento dos relatórios", "End date")
    inicio, fim = df[col_inicio].iloc[0], df[col_fim].iloc[0]
    try:
        inicio_fmt = datetime.strptime(str(inicio), "%Y-%m-%d").strftime("%d/%m/%Y")
        fim_fmt    = datetime.strptime(str(fim),    "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        inicio_fmt, fim_fmt = str(inicio), str(fim)

    def soma(*cols):
        c = _col_opt(df, *cols)
        return round(pd.to_numeric(df[c], errors="coerce").sum(), 2) if c else None

    def media(*cols):
        c = _col_opt(df, *cols)
        return round(pd.to_numeric(df[c], errors="coerce").mean(), 2) if c else None

    return {
        "periodo":    f"{inicio_fmt} - {fim_fmt}",
        "campanha":   df[_col(df, "Nome da campanha")].iloc[0],
        "alcance":    int(pd.to_numeric(df[_col(df, "Alcance")], errors="coerce").sum()),
        "impressoes": int(pd.to_numeric(df[_col(df, "Impressoes", "Impressões")], errors="coerce").sum()),
        "cliques":    soma("Cliques no link"),
        "gasto":      round(pd.to_numeric(df[_col(df, "Valor usado (BRL)")], errors="coerce").sum(), 2),
        "resultados": int(pd.to_numeric(df[_col(df, "Resultados")], errors="coerce").sum()),
        "frequencia": media("Frequencia", "Frequência"),
        "ctr":        media("CTR (taxa de cliques no link)"),
        "cpc":        media("CPC (custo por clique no link)"),
        "cpm":        media("CPM (custo por 1.000 impressoes)", "CPM (custo por 1.000 impressões)"),
        "cpr":        media("Custo por resultado"),
    }

def agrupar_genero(df):
    col_gen     = _col(df, "Genero", "Gênero")
    col_alcance = _col(df, "Alcance")
    col_res     = _col(df, "Resultados")
    col_gasto   = _col(df, "Valor usado (BRL)")
    col_cpr     = _col_opt(df, "Custo por resultado")

    agg = {"alcance": (col_alcance, "sum"), "resultados": (col_res, "sum"), "gasto": (col_gasto, "sum")}
    if col_cpr: agg["cpr"] = (col_cpr, "mean")

    g = df[df[col_gen].isin(["male","female"])].groupby(col_gen).agg(**agg).round(2)
    if "cpr" not in g.columns: g["cpr"] = 0
    return {
        "male":   g.loc["male"].to_dict()   if "male"   in g.index else {},
        "female": g.loc["female"].to_dict() if "female" in g.index else {},
    }

def agrupar_idade(df):
    ordem     = ["18-24","25-34","35-44","45-54","55-64","65+"]
    col_res   = _col(df, "Resultados")
    col_gasto = _col(df, "Valor usado (BRL)")
    col_cpr   = _col_opt(df, "Custo por resultado")

    agg = {"resultados": (col_res, "sum"), "gasto": (col_gasto, "sum")}
    if col_cpr: agg["cpr"] = (col_cpr, "mean")

    presentes = [i for i in ordem if i in df[_col(df, "Idade")].unique()]
    g = df.groupby(_col(df, "Idade")).agg(**agg).round(2).reindex(presentes).fillna(0)
    if "cpr" not in g.columns: g["cpr"] = 0
    return {idx: row.to_dict() for idx, row in g.iterrows()}

def agrupar_anuncio(df):
    col_anuncio = _col(df, "Nome do anuncio", "Nome do anúncio", "Anuncios", "Anúncios")
    col_cliques = _col_opt(df, "Cliques no link")
    col_ctr     = _col_opt(df, "CTR (taxa de cliques no link)")
    col_cpr     = _col_opt(df, "Custo por resultado")

    agg = {
        "resultados": (_col(df, "Resultados"), "sum"),
        "gasto":      (_col(df, "Valor usado (BRL)"), "sum"),
    }
    if col_cliques: agg["cliques"] = (col_cliques, "sum")
    if col_ctr:     agg["ctr"]     = (col_ctr, "mean")
    if col_cpr:     agg["cpr"]     = (col_cpr, "mean")

    g = df.groupby(col_anuncio).agg(**agg).round(2).sort_values("resultados", ascending=False).fillna(0)
    for c in ("cliques","ctr","cpr"):
        if c not in g.columns: g[c] = 0
    return {idx: row.to_dict() for idx, row in g.iterrows()}

def agrupar_conjuntos(df):
    col_conj = _col(df, "Nome do conjunto de anuncios", "Nome do conjunto de anúncios")
    result = {}
    for conj in df[col_conj].unique().tolist():
        sub = df[df[col_conj] == conj].copy()
        result[conj] = {
            "metricas": calcular_metricas(sub),
            "genero":   agrupar_genero(sub),
            "idade":    agrupar_idade(sub),
            "anuncios": agrupar_anuncio(sub),
        }
    return result

# ── Leitura da analise ─────────────────────────────────────────────────────────

def ler_analise(txt_path):
    with open(txt_path, encoding="utf-8") as f:
        return f.read()

def analise_para_html(texto):
    html = ""
    for linha in texto.splitlines():
        s = linha.strip()
        if not s:
            html += "<br>"
        elif s.startswith("-"):
            html += f'<li>{s[1:].strip()}</li>\n'
        elif len(s) < 40 and not s.endswith("."):
            html += f'<h3 class="analise-secao">{s}</h3>\n'
        else:
            html += f'<p>{s}</p>\n'
    html = re.sub(r'(<li>.*?</li>\n)+', lambda m: f'<ul>{m.group(0)}</ul>\n', html, flags=re.DOTALL)
    return html

# ── Formatadores ───────────────────────────────────────────────────────────────

def brl(v):
    if v is None: return "N/D"
    return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")

def intfmt(v):
    if v is None: return "N/D"
    return f"{int(v):,}".replace(",",".")

def fmtopt(v, suffix=""):
    if v is None or v == 0: return "—"
    return f"{v:.2f}{suffix}"

# ── Blocos HTML reutilizaveis ──────────────────────────────────────────────────

def cards_html(m):
    return f"""
    <div class="cards">
      <div class="card">
        <div class="card-label">Alcance</div>
        <div class="card-value">{intfmt(m['alcance'])}</div>
        <div class="card-sub">pessoas unicas</div>
      </div>
      <div class="card">
        <div class="card-label">Impressões</div>
        <div class="card-value">{intfmt(m['impressoes'])}</div>
        <div class="card-sub">freq. media {fmtopt(m.get('frequencia'), 'x')}</div>
      </div>
      <div class="card">
        <div class="card-label">Cliques no link</div>
        <div class="card-value">{intfmt(m['cliques']) if m.get('cliques') is not None else 'N/D'}</div>
        <div class="card-sub">CTR medio {fmtopt(m.get('ctr'), '%')}</div>
      </div>
      <div class="card">
        <div class="card-label">Gasto total</div>
        <div class="card-value">{brl(m['gasto'])}</div>
        <div class="card-sub">orcamento mensal</div>
      </div>
      <div class="card">
        <div class="card-label">Resultados</div>
        <div class="card-value">{intfmt(m['resultados'])}</div>
        <div class="card-sub">conversas iniciadas</div>
      </div>
      <div class="card accent">
        <div class="card-label">Custo / resultado</div>
        <div class="card-value">{brl(m.get('cpr'))}</div>
        <div class="card-sub">por conversa</div>
      </div>
      <div class="card">
        <div class="card-label">CPC</div>
        <div class="card-value">{brl(m.get('cpc'))}</div>
        <div class="card-sub">por clique</div>
      </div>
      <div class="card">
        <div class="card-label">CPM</div>
        <div class="card-value">{brl(m.get('cpm'))}</div>
        <div class="card-sub">por mil impressoes</div>
      </div>
    </div>"""

def tabela_anuncios_html(anuncios):
    total_res = sum(v["resultados"] for v in anuncios.values()) or 1
    max_res   = max((v["resultados"] for v in anuncios.values()), default=0)
    min_cpr   = min((v["cpr"] for v in anuncios.values() if v.get("cpr",0) > 0), default=0)
    rows = ""
    for nome, v in anuncios.items():
        share = round(v["resultados"] / total_res * 100, 1)
        cpr_str = brl(v["cpr"]) if v.get("cpr",0) > 0 else "—"
        ctr_str = fmtopt(v.get("ctr") or None, "%")
        tag = ""
        if v["resultados"] == max_res and max_res > 0:
            tag = '<span class="badge badge-blue">+ volume</span>'
        elif v.get("cpr",0) > 0 and v["cpr"] == min_cpr:
            tag = '<span class="badge badge-green">+ eficiente</span>'
        rows += f"""
        <tr>
          <td>{nome} {tag}</td>
          <td class="num">{intfmt(v['resultados'])}</td>
          <td class="num">{intfmt(v.get('cliques',0))}</td>
          <td class="num">{brl(v['gasto'])}</td>
          <td class="num">{cpr_str}</td>
          <td class="num">{ctr_str}</td>
          <td><div class="bar-cell"><div class="bar-fill" style="width:{min(share*2,100):.0f}%"></div><span>{share}%</span></div></td>
        </tr>"""
    return f"""
    <div class="table-card">
      <table>
        <thead><tr>
          <th>Anuncio</th><th class="num">Conversas</th><th class="num">Cliques</th>
          <th class="num">Gasto</th><th class="num">CPR</th><th class="num">CTR</th><th>Share</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""

def tabela_idade_html(idade):
    cprs    = [v["cpr"] for v in idade.values() if v.get("cpr",0) > 0]
    min_cpr = min(cprs) if cprs else 0
    max_cpr = max(cprs) if cprs else 0
    rows = ""
    for faixa, v in idade.items():
        rc = ""
        if v.get("cpr",0) == min_cpr and min_cpr > 0: rc = "row-best"
        elif v.get("cpr",0) == max_cpr and max_cpr > 0: rc = "row-worst"
        rows += f"""
        <tr class="{rc}">
          <td>{faixa}</td>
          <td class="num">{intfmt(v['resultados'])}</td>
          <td class="num">{brl(v['gasto'])}</td>
          <td class="num">{fmtopt(v.get('ctr') or None, '%')}</td>
          <td class="num">{brl(v['cpr']) if v.get('cpr',0) > 0 else '—'}</td>
        </tr>"""
    return f"""
    <div class="table-card">
      <table>
        <thead><tr>
          <th>Faixa etaria</th><th class="num">Conversas</th>
          <th class="num">Gasto</th><th class="num">CTR</th><th class="num">CPR</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <p class="table-note">Verde = melhor CPR &nbsp;·&nbsp; Vermelho = pior CPR</p>"""

def charts_block(slug, genero, idade):
    masc = genero.get("male", {})
    fem  = genero.get("female", {})
    labels  = list(idade.keys())
    res_data = [idade[k]["resultados"] for k in labels]
    cpr_data = [round(idade[k].get("cpr",0), 2) for k in labels]
    cprs_pos = [v for v in cpr_data if v > 0]
    min_cpr  = min(cprs_pos) if cprs_pos else 0
    max_cpr  = max(cprs_pos) if cprs_pos else 0

    html = f"""
    <div class="section-label">Publico — genero e faixa etaria</div>
    <div class="charts-row">
      <div class="chart-card">
        <div class="chart-title">Genero</div>
        <div class="legend">
          <span><span class="swatch" style="background:#185FA5"></span>Masculino</span>
          <span><span class="swatch" style="background:#D4537E"></span>Feminino</span>
        </div>
        <div class="chart-wrap"><canvas id="cg_{slug}"></canvas></div>
      </div>
      <div class="chart-card">
        <div class="chart-title">Conversas por faixa etaria</div>
        <div class="legend"><span><span class="swatch" style="background:#1D9E75"></span>Conversas</span></div>
        <div class="chart-wrap"><canvas id="ci_{slug}"></canvas></div>
      </div>
    </div>
    <div class="section-label">Custo por resultado por faixa etaria</div>
    <div class="chart-card">
      <div class="chart-title">CPR (R$) — menor e melhor</div>
      <div class="legend">
        <span><span class="swatch" style="background:#1D9E75"></span>Melhor</span>
        <span><span class="swatch" style="background:#378ADD"></span>Intermediario</span>
        <span><span class="swatch" style="background:#E24B4A"></span>Pior</span>
      </div>
      <div class="chart-wrap-h"><canvas id="ccpr_{slug}"></canvas></div>
    </div>"""

    script = f"""
  (function(){{
    const CZ="#888780", AZUL="#185FA5", AM="#378ADD", VERDE="#1D9E75",
          GC="#9FE1CB", ROSA="#D4537E", VERM="#E24B4A";
    const base = {{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}}}};
    new Chart(document.getElementById("cg_{slug}"),{{
      type:"bar",
      data:{{labels:["Alcance","Conversas","Gasto (R$)"],
        datasets:[
          {{label:"Masculino",data:[{masc.get('alcance',0)},{masc.get('resultados',0)},{round(masc.get('gasto',0),0)}],backgroundColor:AZUL,borderRadius:4}},
          {{label:"Feminino", data:[{fem.get('alcance',0)},{fem.get('resultados',0)},{round(fem.get('gasto',0),0)}], backgroundColor:ROSA,borderRadius:4}}
        ]}},
      options:{{...base,scales:{{x:{{ticks:{{color:CZ,font:{{size:11}}}},grid:{{display:false}}}},y:{{ticks:{{color:CZ,font:{{size:10}}}},grid:{{color:"#E8E7E2"}}}}}}}}
    }});
    new Chart(document.getElementById("ci_{slug}"),{{
      type:"bar",
      data:{{labels:{json.dumps(labels)},
        datasets:[{{label:"Conversas",data:{json.dumps(res_data)},backgroundColor:VERDE,borderRadius:4}}]}},
      options:{{...base,scales:{{x:{{ticks:{{color:CZ,font:{{size:11}}}},grid:{{display:false}}}},y:{{ticks:{{color:CZ,font:{{size:10}}}},grid:{{color:"#E8E7E2"}}}}}}}}
    }});
    const cprs={json.dumps(cpr_data)};
    new Chart(document.getElementById("ccpr_{slug}"),{{
      type:"bar",
      data:{{labels:{json.dumps(labels)},
        datasets:[{{label:"CPR",data:cprs,backgroundColor:cprs.map(v=>v==={min_cpr}&&v>0?VERDE:v==={max_cpr}&&v>0?VERM:AM),borderRadius:4}}]}},
      options:{{...base,indexAxis:"y",
        scales:{{x:{{ticks:{{color:CZ,font:{{size:10}},callback:v=>"R$ "+v.toFixed(2).replace(".",",")}},grid:{{color:"#E8E7E2"}}}},y:{{ticks:{{color:CZ,font:{{size:11}}}},grid:{{display:false}}}}}},
        plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>" R$ "+c.parsed.x.toFixed(2).replace(".",",")}}}}}},
      }}
    }});
  }})();"""
    return html, script

def bloco_aba(slug, dados):
    m   = dados["metricas"]
    gen = dados["genero"]
    ida = dados["idade"]
    anu = dados["anuncios"]
    charts_h, charts_s = charts_block(slug, gen, ida)
    content = (
        cards_html(m)
        + '<div class="section-label">Desempenho por anuncio</div>'
        + tabela_anuncios_html(anu)
        + '<div class="section-label">Desempenho por faixa etaria</div>'
        + tabela_idade_html(ida)
        + charts_h
    )
    return content, charts_s

# ── Template HTML principal ────────────────────────────────────────────────────

def gerar_html(m_geral, gen_geral, ida_geral, anu_geral, conjuntos, analise_html, periodo):
    def slug(s):
        return re.sub(r"[^a-z0-9]","_", s.lower())[:20]

    tab_btns   = ['<button class="tab-btn active" data-tab="geral">Visao Geral</button>']
    tab_panels = []
    all_scripts = []

    # Aba geral
    content_g, script_g = bloco_aba("geral", {"metricas": m_geral, "genero": gen_geral, "idade": ida_geral, "anuncios": anu_geral})
    tab_panels.append(f'<div class="tab-panel active" id="tab-geral">{content_g}</div>')
    all_scripts.append(script_g)

    # Abas por conjunto
    for nome, dados in conjuntos.items():
        s     = slug(nome)
        label = re.sub(r"[\[\]]","", nome).strip()
        tab_btns.append(f'<button class="tab-btn" data-tab="{s}" title="{label}">{label}</button>')
        content_c, script_c = bloco_aba(s, dados)
        tab_panels.append(f'<div class="tab-panel" id="tab-{s}">{content_c}</div>')
        all_scripts.append(script_c)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Relatorio de Trafego · {periodo}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&family=DM+Mono&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --azul:#185FA5;--azul-med:#378ADD;--azul-clr:#E6F1FB;
  --verde:#1D9E75;--verde-clr:#EAF3DE;
  --verm:#E24B4A;--verm-clr:#FCEBEB;
  --rosa:#D4537E;
  --esc:#1A1A18;--med:#5C5B57;--clr:#888780;
  --bg:#F4F3EF;--bg2:#ECEAE4;--branco:#FFFFFF;--brd:#D6D4CC;
  --r:12px;--font:'DM Sans',sans-serif;--mono:'DM Mono',monospace;
}}
body{{font-family:var(--font);background:var(--bg);color:var(--esc);font-size:14px;line-height:1.6}}

.topbar{{background:var(--esc);color:#fff;padding:.875rem 2rem;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:200}}@media(max-width:480px){{.topbar{{padding:.75rem 1rem;gap:.5rem}}.topbar-period{{display:none}}}}
.topbar-title{{font-size:13px;font-weight:600;letter-spacing:.03em}}
.topbar-period{{font-size:12px;opacity:.5;font-family:var(--mono)}}

.page{{max-width:1140px;margin:0 auto;padding:2rem 1.5rem 4rem}}@media(max-width:480px){{.page{{padding:1.25rem 1rem 3rem}}}}

.tabs-bar{{display:flex;gap:4px;margin-bottom:1.75rem;border-bottom:2px solid var(--brd);flex-wrap:wrap}}@media(max-width:600px){{.tabs-bar{{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none;padding-bottom:0}}.tabs-bar::-webkit-scrollbar{{display:none}}}}
.tab-btn{{
  font-family:var(--font);font-size:13px;font-weight:500;
  padding:.5rem 1.1rem;border:none;background:transparent;
  color:var(--clr);cursor:pointer;border-bottom:2px solid transparent;
  margin-bottom:-2px;border-radius:6px 6px 0 0;
  transition:color .15s,background .15s;
  white-space:nowrap;max-width:240px;overflow:hidden;text-overflow:ellipsis;flex-shrink:0;
}}
.tab-btn:hover{{color:var(--esc);background:var(--bg2)}}
.tab-btn.active{{color:var(--azul);border-bottom-color:var(--azul);font-weight:600}}
.tab-panel{{display:none}}.tab-panel.active{{display:block}}

.section-label{{
  font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
  color:var(--clr);margin:2.5rem 0 1rem;display:flex;align-items:center;gap:10px;
}}
.section-label::after{{content:"";flex:1;height:1px;background:var(--brd)}}

.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:10px}}@media(max-width:420px){{.cards{{grid-template-columns:1fr 1fr}}}}
.card{{background:var(--branco);border-radius:var(--r);border:1px solid var(--brd);padding:1rem 1.1rem;transition:box-shadow .15s}}
.card:hover{{box-shadow:0 2px 8px rgba(0,0,0,.06)}}
.card.accent{{border-color:var(--azul-med);background:var(--azul-clr)}}
.card-label{{font-size:11px;color:var(--clr);margin-bottom:4px}}
.card-value{{font-size:21px;font-weight:600;color:var(--esc);line-height:1.1;font-family:var(--mono)}}@media(max-width:380px){{.card-value{{font-size:17px}}}}
.card-sub{{font-size:11px;color:var(--clr);margin-top:3px}}

.charts-row{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
@media(max-width:680px){{.charts-row{{grid-template-columns:1fr}}}}
.chart-card{{background:var(--branco);border-radius:var(--r);border:1px solid var(--brd);padding:1.25rem}}
.chart-title{{font-size:10px;font-weight:700;color:var(--clr);margin-bottom:.75rem;letter-spacing:.08em;text-transform:uppercase}}
.chart-wrap{{position:relative;height:220px}}
.chart-wrap-h{{position:relative;height:190px}}
.legend{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:.6rem;font-size:11px;color:var(--clr)}}
.legend span{{display:flex;align-items:center;gap:5px}}
.swatch{{width:9px;height:9px;border-radius:2px;display:inline-block;flex-shrink:0}}

.table-card{{background:var(--branco);border-radius:var(--r);border:1px solid var(--brd);overflow:hidden}}@media(max-width:680px){{.table-card{{overflow-x:auto;-webkit-overflow-scrolling:touch}}  .table-card table{{min-width:540px}}}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
thead th{{background:var(--azul);color:#fff;font-weight:600;font-size:10px;letter-spacing:.06em;text-transform:uppercase;padding:10px 12px;text-align:left;white-space:nowrap}}
thead th.num{{text-align:right}}
tbody tr{{border-bottom:1px solid var(--bg2)}}
tbody tr:last-child{{border-bottom:none}}
tbody tr:nth-child(even){{background:#FAFAF8}}
tbody td{{padding:9px 12px;color:var(--esc);vertical-align:middle}}
tbody td.num{{text-align:right;font-family:var(--mono);font-size:12px}}
.row-best td{{background:var(--verde-clr)!important}}
.row-worst td{{background:var(--verm-clr)!important}}
.badge{{display:inline-block;font-size:10px;font-weight:600;padding:2px 7px;border-radius:20px;margin-left:6px;vertical-align:middle}}
.badge-blue{{background:var(--azul-clr);color:var(--azul)}}
.badge-green{{background:var(--verde-clr);color:var(--verde)}}
.bar-cell{{display:flex;align-items:center;gap:8px;min-width:90px}}
.bar-fill{{height:5px;border-radius:3px;background:var(--azul-med);flex-shrink:0}}
.bar-cell span{{font-size:11px;color:var(--clr);white-space:nowrap}}
.table-note{{font-size:11px;color:var(--clr);margin-top:5px}}

.analise-card{{background:var(--branco);border-radius:var(--r);border:1px solid var(--brd);padding:1.75rem 2rem;line-height:1.8}}@media(max-width:480px){{.analise-card{{padding:1.25rem 1.1rem}}}}
.analise-card h3.analise-secao{{font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--clr);margin:1.5rem 0 .5rem;padding-bottom:6px;border-bottom:1px solid var(--brd)}}
.analise-card h3.analise-secao:first-child{{margin-top:0}}
.analise-card p{{margin-bottom:.5rem;font-size:14px}}
.analise-card ul{{padding-left:1.25rem;margin-bottom:.5rem}}
.analise-card li{{margin-bottom:.25rem;font-size:14px}}

.footer{{text-align:center;font-size:11px;color:var(--clr);margin-top:3rem;padding-top:1.5rem;border-top:1px solid var(--brd);font-family:var(--mono)}}

@media print{{
  .topbar{{position:static}}
  .tabs-bar{{display:none}}
  .tab-panel{{display:block!important;page-break-before:always}}
  .tab-panel:first-child{{page-break-before:auto}}
  body{{background:white}}
}}
</style>
</head>
<body>
<div class="topbar">
  <span class="topbar-title">Relatorio de Trafego Pago · Meta Ads</span>
  <span class="topbar-period">{periodo}</span>
</div>
<div class="page">
  <div class="tabs-bar">{''.join(tab_btns)}</div>
  {''.join(tab_panels)}
  <div class="section-label">Analise</div>
  <div class="analise-card">{analise_html}</div>
  <div class="footer">Feito por Kalleb · {periodo}</div>
</div>
<script>
document.querySelectorAll(".tab-btn").forEach(btn=>{{
  btn.addEventListener("click",()=>{{
    document.querySelectorAll(".tab-btn").forEach(b=>b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p=>p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-"+btn.dataset.tab).classList.add("active");
  }});
}});
{''.join(all_scripts)}
</script>
</body>
</html>"""

# ── Main ───────────────────────────────────────────────────────────────────────

def gerar_relatorio(csv_path, txt_path, output_path):
    df         = carregar_dados(csv_path)
    m_geral    = calcular_metricas(df)
    gen_geral  = agrupar_genero(df)
    ida_geral  = agrupar_idade(df)
    anu_geral  = agrupar_anuncio(df)
    conjuntos  = agrupar_conjuntos(df)
    analise_html = analise_para_html(ler_analise(txt_path))
    html = gerar_html(m_geral, gen_geral, ida_geral, anu_geral, conjuntos, analise_html, m_geral["periodo"])
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Relatorio gerado: {output_path}")

if __name__ == "__main__":
    base     = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base, "dados.csv")
    txt_path = os.path.join(base, "analise.txt")
    out_path = os.path.join(base, "relatorio_trafego.html")

    if not os.path.exists(csv_path):
        print("Erro: 'dados.csv' nao encontrado na pasta do script.")
        sys.exit(1)
    if not os.path.exists(txt_path):
        print("Erro: 'analise.txt' nao encontrado na pasta do script.")
        sys.exit(1)

    gerar_relatorio(csv_path, txt_path, out_path)
