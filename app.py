"""
Backend Flask — Gerador de Relatório de Tráfego Pago
"""

import os, tempfile
from flask import Flask, request, jsonify, send_from_directory
from gerar_relatorio_html import carregar_dados, calcular_metricas, agrupar_genero, \
    agrupar_idade, agrupar_anuncio, agrupar_conjuntos, analise_para_html, gerar_html, ler_analise

app = Flask(__name__, static_folder="static", static_url_path="")

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/gerar", methods=["POST"])
def gerar():
    # Valida arquivos
    if "csv" not in request.files:
        return jsonify({"erro": "Arquivo CSV não enviado."}), 400
    if "analise" not in request.files and "analise_texto" not in request.form:
        return jsonify({"erro": "Análise não enviada."}), 400

    csv_file = request.files["csv"]
    if csv_file.filename == "":
        return jsonify({"erro": "Nenhum arquivo CSV selecionado."}), 400

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Salva CSV
            csv_path = os.path.join(tmpdir, "dados.csv")
            csv_file.save(csv_path)

            # Salva análise (arquivo ou texto digitado)
            txt_path = os.path.join(tmpdir, "analise.txt")
            if "analise" in request.files and request.files["analise"].filename:
                request.files["analise"].save(txt_path)
            else:
                texto = request.form.get("analise_texto", "").strip()
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(texto)

            # Processa
            df         = carregar_dados(csv_path)
            m_geral    = calcular_metricas(df)
            gen_geral  = agrupar_genero(df)
            ida_geral  = agrupar_idade(df)
            anu_geral  = agrupar_anuncio(df)
            conjuntos  = agrupar_conjuntos(df)
            analise_html = analise_para_html(ler_analise(txt_path))

            html = gerar_html(
                m_geral, gen_geral, ida_geral, anu_geral,
                conjuntos, analise_html, m_geral["periodo"]
            )

            from flask import Response
            import json as _json
            payload = _json.dumps({"html": html, "periodo": m_geral["periodo"]}, ensure_ascii=False)
            return Response(payload, mimetype="application/json")

    except KeyError as e:
        return jsonify({"erro": f"Coluna não encontrada no CSV: {e}"}), 422
    except ValueError as e:
        return jsonify({"erro": str(e)}), 422
    except Exception as e:
        return jsonify({"erro": f"Erro inesperado: {str(e)}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
