from flask import Flask, render_template
import json
import os
import time

app = Flask(__name__)

# Caminho para os ficheiros JSON
EMPIRE_JSON_PATH = "/tmp/ikalogs/empire.json"
STATUS_SUMMARY_JSON_PATH = "/tmp/ikalogs/statusSummary.json"

def get_last_modified_date(filepath):
    """Retorna a data de última modificação do ficheiro JSON."""
    if os.path.exists(filepath):
        modified_time = os.path.getmtime(filepath)  # Última modificação
        return time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(modified_time))
    return "Desconhecida"

@app.route("/")
def index():
    # Verifica se o ficheiro empire.json existe
    if not os.path.exists(EMPIRE_JSON_PATH):
        return "Ficheiro empire.json não encontrado!", 404

    # Verifica se o ficheiro statusSummary.json existe
    if not os.path.exists(STATUS_SUMMARY_JSON_PATH):
        return "Ficheiro statusSummary.json não encontrado!", 404

    # Carrega os dados do ficheiro empire.json
    with open(EMPIRE_JSON_PATH, "r") as file:
        empire_data = json.load(file)

    # Carrega os dados do ficheiro statusSummary.json
    with open(STATUS_SUMMARY_JSON_PATH, "r") as file:
        status_summary = json.load(file)

    # Obtém a última modificação do empire.json
    last_updated = get_last_modified_date(EMPIRE_JSON_PATH)

    # Nomes dos materiais em inglês (ajuste conforme necessário)
    materials_names_english = ["Wood", "Wine", "Marble", "Crystal", "Sulfur"]

    # Passa os dados e a última atualização para o template
    return render_template(
        "index.html",
        empire_data=empire_data,
        status_summary=status_summary,
        last_updated=last_updated,
        materials_names_english=materials_names_english,
    )

if __name__ == "__main__":
    app.run(debug=True)