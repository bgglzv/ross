# Comparação feature-motor × feature-motor-bose × feature-motor-bose-arismar

Esta branch **não contém código do ROSS**. Ela guarda o que é preciso para comparar, em outra máquina, as três versões dos acionamentos V/f e FOC:

- `arismar/Codigos_MIT-SVPWM_Final/` — código original do Arismar (V/f e FOC, versão 2), sem alterações.
- `harness/` — scripts que executam o código do Arismar e as três versões do ROSS com os mesmos parâmetros, calculam métricas (THD, ripple, partida, regime), geram figuras e o relatório.
- `report/` — relatório comparativo (`.md` e `.docx`), figuras e métricas do caso já executado.

As três versões do ROSS vêm das branches do seu fork:

| Pasta criada | Origem |
|---|---|
| `cmp_jg` | commit `0ec7dad5` (feature-motor do jguarato) |
| `cmp_bose` | branch `feature-motor-bose` |
| `cmp_arismar` | branch `feature-motor-bose-arismar` |

## Uso rápido

Com o seu clone (`ross`, em qualquer branch) já com `git fetch origin`:

```bash
cd ross
git worktree add ../comparacao origin/comparacao-arismar   # esta branch, em uma pasta ao lado
cd ../comparacao
python harness/setup_worktrees.py        # cria ../cmp_jg, ../cmp_bose, ../cmp_arismar
python harness/run_all.py --paralelo 8   # caso do relatório (NS = 100, 3 s)
python harness/run_all.py --passo        # opcional: sensibilidade ao passo (NS = 20 e 40)
```

Use o Python em que o ROSS e as suas dependências estão instalados (numpy, numba, plotly, matplotlib). Os worktrees são criados "detached", então não competem com a branch que você estiver usando no clone.

Isso deixa o código do Arismar disponível em `../comparacao/arismar/` sem sujar as branches de código. Se preferir tê-lo dentro da própria branch em que está trabalhando, sem versionar:

```bash
git restore --source=origin/comparacao-arismar --worktree -- arismar harness report
printf 'arismar/\nharness/\nreport/\nruns/\n' >> .git/info/exclude
```

## O caso executado

Motor de `motor_example()` (1,5 cv, 4 pólos, 1710 rpm), barramento CC de 296,96 V, chaveamento de 5 kHz, passo de 2e-6 s (`--ns 100`), 3 s, referência de 60 Hz (1800 rpm síncronos), carga de 6,16 N·m aplicada em 1 s, rampa de 0,6667 s. As grandezas de regime são medidas entre 2 s e 3 s. A janela de análise (`analyze.py`: `WINDOW`, `T_LOAD`) está fixa nesses valores; se mudar `--t-total` ou `--t-carga`, ajuste-a.

Variantes executadas:

| Nome | O que é |
|---|---|
| `standalone` | código do Arismar sem gráficos, mesmos parâmetros (referência) |
| `jg` | feature-motor, opções padrão |
| `bose` | feature-motor-bose; no FOC com `frequency_max = 60 Hz` (referência síncrona) |
| `ari` | feature-motor-bose-arismar; no FOC com `ids_ref = 3,2 A` (valor de `main_foc_v2.py`) |
| `ari_def` | igual a `ari`, mas com o `ids_ref` calculado (3,78 A) |
| `ari_rsc` | igual a `ari`, com a resistência de curto-circuito da rede igualada à do código do Arismar |

## Scripts

| Script | Função |
|---|---|
| `setup_worktrees.py` | cria as três versões do ROSS ao lado do repositório |
| `run_all.py` | roda as simulações em paralelo e chama a análise |
| `run_standalone.py` | roda o código do Arismar (`VF` ou `FOC`) |
| `run_ross.py` | roda uma versão do ROSS (`run_with_inverter_vf/foc`) |
| `analyze.py` | métricas, validação contra o código do Arismar e figuras |
| `passo.py` | sensibilidade ao passo (após `--passo`) |
| `diag_modulacao.py` | fração de períodos sobremodulados/saturados no FOC (`python harness/diag_modulacao.py 3.2` e `... calc`) |
| `cmp_bose.py` | compara a sobremodulação de Bose das duas implementações |
| `make_report.py` | regenera as tabelas do relatório (`report/relatorio_comparativo_arismar_regenerado.md`) |
| `config.py` | caminhos; use `ROSS_COMPARACAO_RAIZ` para mudar a pasta onde ficam `cmp_*` |

`make_report.py` recalcula as tabelas a partir das métricas, mas os números do texto das seções 5.3 e 6 do relatório são fixos (vêm do caso do relatório); leia o relatório regenerado com isso em mente.

## Notas

- A validação do V/f exige coincidência amostra a amostra com o código do Arismar (`report/metricas.json`, `port_vs_standalone`). No FOC, a coincidência é de algumas dezenas de milhares de amostras, e depois só estatística (sensibilidade numérica do laço fechado).
- Tempo aproximado com `--ns 100`: 2 a 6 minutos por simulação; o código do Arismar (Python puro) é o mais lento.
- `runs/` (arquivos `.npz`, centenas de MB) não é versionado.
