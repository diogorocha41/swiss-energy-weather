# Guia rápido (PT)

## 1. Preparar o ambiente
```bash
cd swiss-energy-weather
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
pytest -q                        # devem passar 8 testes
```

## 2. Descarregar os ficheiros da Swissgrid
1. Abre https://www.swissgrid.ch/en/home/customers/topics/energy-data-ch.html
2. Na secção de downloads, descarrega os XLSX «Energy Statistic Switzerland» de **2019 a 2026**.
3. Guarda-os em `data/raw/swissgrid/` (o nome do ficheiro não importa).

## 3. Correr o pipeline
```bash
python -m src.pipeline all
```
- A primeira execução demora alguns minutos: lê os Excel e descarrega os dados das 6 estações da MeteoSwiss.
- As execuções seguintes só processam o que mudou.
- No fim aparecem os testes de qualidade (`OK`, `WARN` ou `FAIL`).

## 4. Abrir o dashboard
```bash
streamlit run dashboard/app.py
```

## 5. Se der erro
Os pontos mais prováveis de ajuste na primeira execução:
- **Nomes das colunas da Swissgrid**: estão definidos em `SWISSGRID_SERIES` no ficheiro `src/config.py`.
- **Nomes dos ficheiros da MeteoSwiss**: são escolhidos pela função `select_hourly_assets`.
- **Teste `assert_plausible_hourly_load` a falhar**: normalmente é um problema de unidades ou uma coluna mal mapeada.
