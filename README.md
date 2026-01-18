# Extrator de PDF para Markdown

Ferramenta para extração de texto de arquivos PDF em formato **Markdown**, utilizando a biblioteca [Docling](https://www.docling.ai/).

## Funcionalidades

- ✅ Extração de PDFs individuais ou em lote
- ✅ Saída em formato Markdown (preserva tabelas, listas, formatação)
- ✅ Tags `<PAGINA:nnn>` para identificar páginas
- ✅ Tags `<IMAGEM:nnn>` para marcar posição de imagens
- ✅ Processamento recursivo de subpastas
- ✅ Logs detalhados por arquivo e geral
- ✅ Pasta de logs separada (opcional)
- ✅ Suporte a OCR e detecção de tabelas (opcional)

## Instalação

### Dependências obrigatórias

```bash
pip install -r requirements.txt
```

Ou manualmente:

```bash
pip install docling pyyaml regex
```

### Dependências opcionais

Para habilitar recursos avançados (OCR e detecção de estrutura de tabelas), instale:

#### Linux/WSL

```bash
# Biblioteca gráfica para OpenCV (detecção de tabelas)
sudo apt-get update
sudo apt-get install -y libglib2.0-0 libgl1

# Tesseract OCR (para PDFs escaneados)
sudo apt-get install -y tesseract-ocr tesseract-ocr-por
```

#### macOS

```bash
brew install tesseract tesseract-lang
```

#### Windows

1. Baixe e instale o [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
2. Adicione ao PATH do sistema

> **Nota:** Se as dependências opcionais não estiverem instaladas, a extração funciona normalmente, mas sem OCR e detecção avançada de tabelas. Use `ignorar_dependencias: true` no YAML para continuar sem erros.

## Testando com Exemplos

O projeto já inclui arquivos de exemplo para teste. Para executá-los:

1. Acesse a pasta do código fonte:
   ```bash
   cd src
   ```

2. Execute o script com a configuração de exemplo:
   ```bash
   python extrair_pdf.py config_exemplos.yaml
   ```

Isso processará os PDFs em `src/pdfs_exemplos` e salvará os resultados em `src/textos_exemplos`.

## Uso em seus projetos

### Configuração

1. Crie uma pasta para seus PDFs (ex: `meus_pdfs`).
2. Copie e edite o arquivo de configuração ou use o modelo abaixo (`meu_config.yaml`):

```yaml
pasta_origem: ./meus_pdfs
pasta_destino: ./meus_textos
subpastas: true
ignorar_dependencias: true
```

### Execução

A partir da pasta `src`:

```bash
python extrair_pdf.py ../meu_config.yaml
```

Ou arquivo individual:

```bash
python extrair_pdf.py ../meus_pdfs/documento.pdf
```

## Estrutura sugerida do projeto

```
.
├── config.yaml          # Arquivo de configuração
├── pdfs/                # Coloque seus PDFs aqui (crie a pasta)
├── textos/              # Os textos extraídos aparecerão aqui
├── logs/                # Logs de processamento
├── src/                 # Código fonte
│   └── extrair_pdf.py   # Script principal
├── requirements.txt     # Dependências
└── README.md
```

## Configuração YAML

O arquivo `config.yaml` controla o processo:

```yaml
# Pasta contendo os PDFs (obrigatório)
pasta_origem: ./pdfs

# Pasta de destino (padrão: pasta_origem)
pasta_destino: ./textos

# Pasta para logs (padrão: pasta_destino)
pasta_log: ./logs

# Processar subpastas? (padrão: true)
subpastas: true

# Sobrescrever existentes? (padrão: false)
sobrescrever: false

# Habilitar OCR (Optical Character Recognition)?
# Se true (padrão): requer Tesseract instalado. Se não tiver, o processamento para.
# Se false: ignora OCR se Tesseract não estiver disponível
ocr: true

# Habilitar detecção avançada de tabelas?
# Se true (padrão): requer libGL/OpenCV instalado (=sudo apt install libgl1).
# Se false: ignora tabelas se libGL não estiver disponível
detectar_tabelas: true

# Ignorar dependências opcionais? (padrão: true)
# true = continua se faltarem dependências não críticas
# false = interrompe com erro
ignorar_dependencias: true
```

## Estrutura de saída

### Com logs na mesma pasta (padrão)

```
textos/
├── documento1.md          # Texto extraído em Markdown
├── documento1.log         # Log individual
├── documento2.md
├── documento2.log
└── log_extração.txt       # Log geral do processamento
```

### Com logs em pasta separada

```yaml
pasta_destino: ./textos
pasta_log: ./logs
```

```
textos/
├── documento1.md
├── documento2.md
└── ...

logs/
├── documento1.log
├── documento2.log
└── log_extração.txt
```

## Exemplo de saída Markdown

```markdown
<PAGINA:001>

# Título do Documento

Este é um parágrafo de exemplo extraído do PDF.

| Coluna 1 | Coluna 2 | Coluna 3 |
|----------|----------|----------|
| Dado 1   | Dado 2   | Dado 3   |

<IMAGEM:001>

<PAGINA:002>

## Seção 2

Continuação do documento...
```

## Verificando dependências

Para verificar se as dependências opcionais estão instaladas:

```bash
# Verificar libGL/OpenCV
python -c "import cv2; print('OpenCV OK')"

# Verificar Tesseract
tesseract --version
```

## Troubleshooting

### Erro: `libGL.so.1: cannot open shared object file`

Instale as bibliotecas gráficas:

```bash
sudo apt-get install -y libgl1-mesa-glx libglib2.0-0
```

### Aviso: `No OCR engine found`

Instale o Tesseract OCR:

```bash
sudo apt-get install -y tesseract-ocr
```

### PDFs escaneados não extraem texto

Verifique se o Tesseract está instalado e se `ignorar_dependencias: false` não está bloqueando a execução.

## Licença

MIT
