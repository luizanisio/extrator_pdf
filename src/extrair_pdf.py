'''
  Autor: Luiz Anísio
  Data: 2025-01-18
  Repositório: https://github.com/luizanisio/extrator_pdf

  Recebe como parâmetro o nome de um arquivo PDF e extrai o texto em formato Markdown 
  utilizando https://www.docling.ai/ 
  
  Se o parâmetro for um yaml, ele processa todos os arquivos PDFs encontrados na pasta_origem.
  Se o arquivo YAML não existir, oferece criar um arquivo modelo.
  
  Parâmetros do yaml:
  - pasta_origem: o nome da pasta de origem (obrigatório)
  - pasta_destino: o nome da pasta de destino (se vazia, usa a de origem)
  - subpastas: True/False (se True, processa as subpastas) - padrão True
  - sobrescrever: True/False (se True, sobrescreve os arquivos texto existentes) - padrão False
  - ignorar_dependencias: True/False (se True, ignora erros de dependências opcionais) - padrão True

  A extração ocorre em formato Markdown preservando a formatação original (tabelas, listas, etc).
  Tags especiais são adicionadas: <PAGINA:nnn> no início de cada página e <IMAGEM:nnn> para imagens.
  
  O nome do arquivo de saída é o mesmo do arquivo de entrada, mas com a extensão .md.
  Um log de extração é gerado no arquivo log_extração.txt. 
  Um log individual de cada arquivo é gerado no arquivo com o mesmo nome do arquivo de entrada, mas com a extensão .log.
'''

import os
import sys
import regex as re
import yaml
from datetime import datetime
from pathlib import Path

# Verifica dependências obrigatórias
try:
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import PdfFormatOption
    DOCLING_DISPONIVEL = True
except ImportError:
    DOCLING_DISPONIVEL = False

# Verifica dependências opcionais (OCR e detecção de tabelas)
DEPENDENCIAS_OPCIONAIS = {
    'libgl': False,
    'tesseract': False
}

def verificar_dependencias_opcionais():
    """Verifica se as dependências opcionais estão disponíveis e retorna suas versões."""
    global DEPENDENCIAS_OPCIONAIS
    
    # Verifica libGL (necessário para OpenCV/detecção de tabelas)
    try:
        import cv2
        DEPENDENCIAS_OPCIONAIS['libgl'] = f"Instalado (v{cv2.__version__})"
    except ImportError:
        DEPENDENCIAS_OPCIONAIS['libgl'] = False
    except Exception:
        DEPENDENCIAS_OPCIONAIS['libgl'] = False
    
    # Verifica tesseract (necessário para OCR)
    try:
        import subprocess
        result = subprocess.run(['tesseract', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            # Pega a primeira linha da saída (ex: tesseract 5.3.0)
            versao = result.stdout.splitlines()[0]
            DEPENDENCIAS_OPCIONAIS['tesseract'] = versao
        else:
            DEPENDENCIAS_OPCIONAIS['tesseract'] = False
    except:
        DEPENDENCIAS_OPCIONAIS['tesseract'] = False
    
    return DEPENDENCIAS_OPCIONAIS


def criar_dicas_ambiente(pasta_destino: str = None, deps: dict = None):
    """
    Cria arquivo dicas_ambiente.md com status das dependências e instruções se necessário.
    
    Args:
        pasta_destino: Pasta onde criar o arquivo (padrão: diretório atual)
        deps: Dicionário de dependências (se None, verifica automaticamente)
    """
    if deps is None:
        deps = verificar_dependencias_opcionais()
    
    # Define o caminho do arquivo
    if pasta_destino:
        arquivo = Path(pasta_destino) / 'dicas_ambiente.md'
    else:
        arquivo = Path('dicas_ambiente.md')
    
    # Monta o conteúdo
    linhas = [
        "# Rastreabilidade e Dicas de Ambiente",
        "",
        f"Data de verificação: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Status das Dependências",
        ""
    ]
    
    # Adiciona status das dependências
    libgl_status = deps.get('libgl', False)
    if libgl_status:
        linhas.append(f"- **OpenCV/libGL**: ✅ {libgl_status}")
    else:
        linhas.append("- **OpenCV/libGL**: ❌ Não encontrado")

    tesseract_status = deps.get('tesseract', False)
    if tesseract_status:
        linhas.append(f"- **Tesseract OCR**: ✅ {tesseract_status}")
    else:
        linhas.append("- **Tesseract OCR**: ❌ Não encontrado")
    
    linhas.append("")

    # Se falta alguma dependência, adiciona instruções
    if not libgl_status or not tesseract_status:
        linhas.extend([
            "## Instruções de Instalação",
            "",
            "Recursos avançados dependem dos pacotes abaixo:",
            ""
        ])
    
        if not libgl_status:
            linhas.append("### OpenCV/libGL (detecção de tabelas)")
            linhas.append("```bash")
            linhas.append("sudo apt-get install -y libgl1-mesa-glx libglib2.0-0")
            linhas.append("```")
            linhas.append("")
        
        if not tesseract_status:
            linhas.append("### Tesseract OCR (PDFs escaneados)")
            linhas.append("```bash")
            linhas.append("sudo apt-get install -y tesseract-ocr tesseract-ocr-por")
            linhas.append("```")
            linhas.append("")
    
    linhas.extend([
        "---",
        "",
        "📖 Consulte o **README.md** para mais informações.",
        ""
    ])
    
    # Salva o arquivo
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    with open(arquivo, 'w', encoding='utf-8') as f:
        f.write('\n'.join(linhas))
    
    return str(arquivo)

RE_LIMPEZA_REPETICAO = re.compile(r'([.,;+\-_?!:;()\[\]{}|@#$%^&*=~`\'])\1+')
def limpar_texto(texto: str) -> str:
    """Limpa o texto removendo caracteres especiais excessivos e normalizando espaços."""
    # Substitui múltiplos espaços horizontais por um único
    texto = re.sub(r'[ \t]+', ' ', texto)
    # Normaliza quebras de linha (no máximo 2 consecutivas)
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    # Substitui múltiplos caracters especiais pelo mesmo caractere uma vez
    texto = RE_LIMPEZA_REPETICAO.sub(r'\1', texto)
    return texto.strip()

class ExtrairPdf:
    """Classe responsável por extrair texto de um único arquivo PDF em formato Markdown."""
    
    def __init__(self, arquivo_pdf: str, pasta_destino: str = None, 
                 pasta_log: str = None, ignorar_dependencias: bool = True,
                 gerar_dicas: bool = True):
        """
        Inicializa o extrator de PDF.
        
        Args:
            arquivo_pdf: Caminho do arquivo PDF
            pasta_destino: Pasta de destino para os arquivos gerados
            pasta_log: Pasta para os logs (se vazia, usa pasta_destino)
            ignorar_dependencias: Se True, ignora erros de dependências opcionais
            gerar_dicas: Se True, gera arquivo de dicas de ambiente
        """
        self.arquivo_pdf = Path(arquivo_pdf).resolve()
        self.ignorar_dependencias = ignorar_dependencias
        self.gerar_dicas = gerar_dicas
        
        # Define pasta de destino
        if pasta_destino:
            self.pasta_destino = Path(pasta_destino).resolve()
        else:
            self.pasta_destino = self.arquivo_pdf.parent
        
        # Define pasta de log (se não especificada, usa pasta_destino)
        if pasta_log:
            self.pasta_log = Path(pasta_log).resolve()
        else:
            self.pasta_log = self.pasta_destino
        
        # Cria pastas se não existirem
        self.pasta_destino.mkdir(parents=True, exist_ok=True)
        self.pasta_log.mkdir(parents=True, exist_ok=True)
        
        # Define arquivos de saída (agora .md para markdown)
        nome_base = self.arquivo_pdf.stem
        self.arquivo_md = self.pasta_destino / f"{nome_base}.md"
        self.arquivo_log = self.pasta_log / f"{nome_base}.log"
        self.log = []
        
        # Contador de imagens
        self.contador_imagens = 0
        
    def _adicionar_log(self, mensagem: str):
        """Adiciona uma mensagem ao log."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entrada_log = f"[{timestamp}] {mensagem}"
        self.log.append(entrada_log)
        print(entrada_log)
        
    def _salvar_log(self):
        """Salva o log individual do arquivo."""
        with open(self.arquivo_log, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.log))
    
    def _verificar_dependencias(self) -> bool:
        """
        Verifica se as dependências estão disponíveis.
        Retorna False se dependências críticas estiverem faltando e ignorar_dependencias=False.
        """
        if not DOCLING_DISPONIVEL:
            self._adicionar_log("ERRO CRÍTICO: O pacote 'docling' não está instalado.")
            self._adicionar_log("Instale com: pip install docling")
            return False
        
        deps = verificar_dependencias_opcionais()
        
        # Cria arquivo de dicas (rastreabilidade do ambiente)
        if self.gerar_dicas:
            arquivo_dicas = criar_dicas_ambiente(str(self.pasta_log), deps)
            if arquivo_dicas:
                 self._adicionar_log(f"Informações do ambiente salvas em: {arquivo_dicas}")

        
        if not deps['libgl']:
            msg = "AVISO: libGL/OpenCV não disponível - detecção de tabelas desabilitada"
            self._adicionar_log(msg)
            if not self.ignorar_dependencias:
                self._adicionar_log("ERRO: Dependência opcional faltando e ignorar_dependencias=False")
                return False
        
        if not deps['tesseract']:
            msg = "AVISO: Tesseract não disponível - OCR desabilitado"
            self._adicionar_log(msg)
            if not self.ignorar_dependencias:
                self._adicionar_log("ERRO: Dependência opcional faltando e ignorar_dependencias=False")
                return False
        
        return True
    
    def _substituir_imagens_markdown(self, texto_md: str) -> str:
        """Substitui referências de imagens no markdown por tags <IMAGEM:nnn>."""
        # Padrões de imagem em markdown
        padroes = [
            r'!\[([^\]]*)\]\([^\)]+\)',  # ![alt](url)
            r'<img[^>]*>',               # <img ... >
            r'\[image[^\]]*\]',          # [image...]
            r'\[figure[^\]]*\]',         # [figure...]
            r'\[figura[^\]]*\]',         # [figura...]
            r'\[imagem[^\]]*\]',         # [imagem...]
        ]
        
        def substituir(match):
            self.contador_imagens += 1
            return f"<IMAGEM:{self.contador_imagens:03d}>"
        
        texto_processado = texto_md
        for padrao in padroes:
            texto_processado = re.sub(padrao, substituir, texto_processado, flags=re.IGNORECASE)
        
        return texto_processado
    
    def extrair(self) -> bool:
        """
        Extrai o texto do PDF em formato Markdown usando Docling.
        Retorna True se bem-sucedido, False caso contrário.
        """
        self._adicionar_log(f"Iniciando extração: {self.arquivo_pdf}")
        
        # Verifica se o arquivo existe
        if not self.arquivo_pdf.exists():
            self._adicionar_log(f"ERRO: Arquivo não encontrado: {self.arquivo_pdf}")
            self._salvar_log()
            return False
        
        # Verifica dependências
        if not self._verificar_dependencias():
            self._salvar_log()
            return False
        
        try:
            # Configura o conversor
            self._adicionar_log("Inicializando DocumentConverter...")
            
            # Verifica quais features podem ser habilitadas
            deps = verificar_dependencias_opcionais()
            
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = bool(deps['tesseract'])
            pipeline_options.do_table_structure = bool(deps['libgl'])
            
            if deps['tesseract']:
                self._adicionar_log("OCR habilitado (tesseract disponível)")
            if deps['libgl']:
                self._adicionar_log("Detecção de tabelas habilitada (libGL disponível)")
            
            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_options=pipeline_options
                    )
                }
            )
            
            # Converte o documento
            self._adicionar_log("Convertendo documento...")
            resultado = converter.convert(str(self.arquivo_pdf))
            
            # Extrai o documento
            documento = resultado.document
            
            # Processa página por página para adicionar tags
            self._adicionar_log("Processando páginas...")
            
            # Agrupa conteúdo por página
            paginas_conteudo = {}
            
            for item, nivel in documento.iterate_items():
                # Obtém o número da página
                num_pagina = 1
                if hasattr(item, 'prov') and item.prov:
                    for prov in item.prov:
                        if hasattr(prov, 'page_no'):
                            num_pagina = prov.page_no
                            break
                
                # Detecta tipo do item
                tipo_item = type(item).__name__.lower()
                
                # Obtém conteúdo em markdown
                conteudo = ""
                if 'picture' in tipo_item or 'image' in tipo_item or 'figure' in tipo_item:
                    self.contador_imagens += 1
                    conteudo = f"<IMAGEM:{self.contador_imagens:03d}>"
                elif hasattr(item, 'export_to_markdown'):
                    try:
                        conteudo = item.export_to_markdown(documento)
                    except TypeError:
                        try:
                            conteudo = item.export_to_markdown()
                        except:
                            if hasattr(item, 'text') and item.text:
                                conteudo = item.text
                elif hasattr(item, 'text') and item.text:
                    conteudo = item.text
                
                if conteudo:
                    if num_pagina not in paginas_conteudo:
                        paginas_conteudo[num_pagina] = []
                    paginas_conteudo[num_pagina].append(conteudo)
            
            # Monta o markdown final com tags de página
            markdown_final = ""
            
            if paginas_conteudo:
                for num_pagina in sorted(paginas_conteudo.keys()):
                    markdown_final += f"\n<PAGINA:{num_pagina:03d}>\n\n"
                    conteudo_pagina = '\n\n'.join(paginas_conteudo[num_pagina])
                    # Processa referências de imagens que podem ter vindo no markdown
                    conteudo_pagina = self._substituir_imagens_markdown(conteudo_pagina)
                    markdown_final += conteudo_pagina
                    markdown_final += '\n'
            else:
                # Fallback: usa o markdown completo do documento
                self._adicionar_log("Aviso: Não foi possível separar por páginas, usando markdown completo")
                markdown_final = f"<PAGINA:001>\n\n{documento.export_to_markdown()}"
                markdown_final = self._substituir_imagens_markdown(markdown_final)
            
            # Limpeza final do texto
            self._adicionar_log("Aplicando limpeza de texto (ruídos)...")
            markdown_final = limpar_texto(markdown_final)
            
            # Salva o arquivo markdown
            self._adicionar_log(f"Salvando markdown em: {self.arquivo_md}")
            with open(self.arquivo_md, 'w', encoding='utf-8') as f:
                f.write(markdown_final.strip())
            
            # Estatísticas
            num_caracteres = len(markdown_final)
            num_palavras = len(markdown_final.split())
            num_paginas = len(paginas_conteudo) if paginas_conteudo else 1
            
            self._adicionar_log(f"Extração concluída com sucesso!")
            self._adicionar_log(f"  - Páginas: {num_paginas}")
            self._adicionar_log(f"  - Imagens detectadas: {self.contador_imagens}")
            self._adicionar_log(f"  - Caracteres: {num_caracteres}")
            self._adicionar_log(f"  - Palavras: ~{num_palavras}")
            
            self._salvar_log()
            return True
            
        except Exception as e:
            self._adicionar_log(f"ERRO durante extração: {str(e)}")
            import traceback
            self._adicionar_log(f"Traceback: {traceback.format_exc()}")
            self._salvar_log()
            return False


class ListarArquivosPdf:
    """Classe utilitária para listar arquivos PDF em uma pasta."""
    
    @classmethod
    def listar(cls, pasta_origem: str, subpastas: bool = True) -> list:
        """
        Lista todos os arquivos PDF em uma pasta.
        
        Args:
            pasta_origem: Caminho da pasta de origem
            subpastas: Se True, busca recursivamente em subpastas
            
        Returns:
            Lista de caminhos completos dos arquivos PDF encontrados
        """
        pasta = Path(pasta_origem).resolve()
        
        if not pasta.exists():
            print(f"ERRO: Pasta não encontrada: {pasta}")
            return []
        
        if not pasta.is_dir():
            print(f"ERRO: Não é uma pasta: {pasta}")
            return []
        
        # Busca arquivos PDF
        if subpastas:
            arquivos = list(pasta.rglob("*.pdf")) + list(pasta.rglob("*.PDF"))
        else:
            arquivos = list(pasta.glob("*.pdf")) + list(pasta.glob("*.PDF"))
        
        # Remove duplicatas (diferença de case em Windows)
        arquivos_unicos = []
        caminhos_vistos = set()
        for arq in arquivos:
            caminho_normalizado = str(arq).lower()
            if caminho_normalizado not in caminhos_vistos:
                caminhos_vistos.add(caminho_normalizado)
                arquivos_unicos.append(arq)
        
        return sorted(arquivos_unicos)


class ProcessarPasta:
    """Classe para processar múltiplos PDFs de uma pasta baseado em configuração YAML."""
    
    def __init__(self, config_ou_yaml: str = None, pasta_origem: str = None, 
                 pasta_destino: str = None, pasta_log: str = None,
                 subpastas: bool = True, sobrescrever: bool = False, 
                 ignorar_dependencias: bool = True):
        """
        Inicializa o processador de pasta.
        
        Args:
            config_ou_yaml: Caminho para arquivo YAML de configuração (opcional)
            pasta_origem: Pasta de origem (se não usar YAML)
            pasta_destino: Pasta de destino (se não usar YAML)
            pasta_log: Pasta para logs (se não usar YAML, padrão pasta_destino)
            subpastas: Processar subpastas (padrão True)
            sobrescrever: Sobrescrever arquivos existentes (padrão False)
            ignorar_dependencias: Ignorar erros de dependências opcionais (padrão True)
        """
        self.ignorar_dependencias = ignorar_dependencias
        self.pasta_log = None
        
        # Se recebeu um arquivo YAML, carrega as configurações
        if config_ou_yaml and config_ou_yaml.lower().endswith('.yaml'):
            self._carregar_yaml(config_ou_yaml)
        else:
            self.pasta_origem = Path(pasta_origem).resolve() if pasta_origem else None
            self.pasta_destino = Path(pasta_destino).resolve() if pasta_destino else self.pasta_origem
            self.pasta_log = Path(pasta_log).resolve() if pasta_log else None
            self.subpastas = subpastas
            self.sobrescrever = sobrescrever
        
        # Define pasta de log (se não especificada, usa pasta_destino)
        if not self.pasta_log:
            self.pasta_log = self.pasta_destino
        
        # Cria pasta de log se não existir
        if self.pasta_log:
            self.pasta_log.mkdir(parents=True, exist_ok=True)
        
        # Log geral
        if self.pasta_log:
            self.arquivo_log = self.pasta_log / 'log_extração.txt'
        elif self.pasta_origem:
            self.arquivo_log = self.pasta_origem / 'log_extração.txt'
        else:
            self.arquivo_log = Path('log_extração.txt')
        self.log = []
        
        # Estatísticas
        self.total_processados = 0
        self.total_sucesso = 0
        self.total_falha = 0
        self.total_ignorados = 0
    
    def _carregar_yaml(self, caminho_yaml: str):
        """Carrega configurações de um arquivo YAML."""
        with open(caminho_yaml, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        self.pasta_origem = Path(config.get('pasta_origem', '.')).resolve()
        
        pasta_dest = config.get('pasta_destino', '')
        if pasta_dest:
            self.pasta_destino = Path(pasta_dest).resolve()
        else:
            self.pasta_destino = self.pasta_origem
        
        # Pasta de log (se não especificada, usa pasta_destino)
        pasta_log = config.get('pasta_log', '')
        if pasta_log:
            self.pasta_log = Path(pasta_log).resolve()
        else:
            self.pasta_log = None  # será definida depois como pasta_destino
            
        self.subpastas = config.get('subpastas', True)
        self.sobrescrever = config.get('sobrescrever', False)
        self.ignorar_dependencias = config.get('ignorar_dependencias', True)
        
    def _adicionar_log(self, mensagem: str):
        """Adiciona uma mensagem ao log geral."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entrada_log = f"[{timestamp}] {mensagem}"
        self.log.append(entrada_log)
        print(entrada_log)
        
    def _salvar_log(self):
        """Salva o log geral de extração."""
        with open(self.arquivo_log, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.log))
            
    def _calcular_destino(self, arquivo_pdf: Path) -> Path:
        """
        Calcula o caminho de destino para um arquivo, preservando a estrutura de subpastas.
        """
        # Calcula o caminho relativo em relação à pasta de origem
        try:
            caminho_relativo = arquivo_pdf.parent.relative_to(self.pasta_origem)
            pasta_destino_arquivo = self.pasta_destino / caminho_relativo
        except ValueError:
            # Se não conseguir calcular relativo, usa a pasta de destino diretamente
            pasta_destino_arquivo = self.pasta_destino
        
        return pasta_destino_arquivo
    
    def processar(self) -> dict:
        """
        Processa todos os PDFs da pasta de origem.
        
        Returns:
            Dicionário com estatísticas do processamento
        """
        self._adicionar_log("=" * 60)
        self._adicionar_log("INICIANDO PROCESSAMENTO EM LOTE")
        self._adicionar_log("=" * 60)
        self._adicionar_log(f"Pasta de origem: {self.pasta_origem}")
        self._adicionar_log(f"Pasta de destino: {self.pasta_destino}")
        self._adicionar_log(f"Incluir subpastas: {self.subpastas}")
        self._adicionar_log(f"Sobrescrever existentes: {self.sobrescrever}")
        self._adicionar_log(f"Ignorar dependências opcionais: {self.ignorar_dependencias}")
        self._adicionar_log("-" * 60)
        
        # Log das dependências disponíveis
        deps = verificar_dependencias_opcionais()
        self._adicionar_log(f"Dependências: libGL={deps['libgl']}, tesseract={deps['tesseract']}")
        
        # Cria arquivo de dicas (rastreabilidade do ambiente)
        arquivo_dicas = criar_dicas_ambiente(str(self.pasta_log), deps)
        if arquivo_dicas:
            self._adicionar_log(f"Informações do ambiente salvas em: {arquivo_dicas}")

        
        if not self.ignorar_dependencias and (not deps['libgl'] or not deps['tesseract']):
            self._adicionar_log("ERRO: Dependências opcionais faltando e ignorar_dependencias=False")
            self._salvar_log()
            return self._gerar_estatisticas()
        
        self._adicionar_log("-" * 60)
        
        # Cria pasta de destino se não existir
        self.pasta_destino.mkdir(parents=True, exist_ok=True)
        
        # Lista os arquivos PDF
        arquivos = ListarArquivosPdf.listar(str(self.pasta_origem), self.subpastas)
        
        if not arquivos:
            self._adicionar_log("Nenhum arquivo PDF encontrado!")
            self._salvar_log()
            return self._gerar_estatisticas()
        
        self._adicionar_log(f"Arquivos PDF encontrados: {len(arquivos)}")
        self._adicionar_log("-" * 60)
        
        # Processa cada arquivo
        for i, arquivo_pdf in enumerate(arquivos, 1):
            self._adicionar_log(f"\n[{i}/{len(arquivos)}] Processando: {arquivo_pdf.name}")
            
            # Calcula o destino preservando estrutura de pastas
            pasta_destino_arquivo = self._calcular_destino(arquivo_pdf)
            
            # Cria a pasta de destino se necessário
            pasta_destino_arquivo.mkdir(parents=True, exist_ok=True)
            
            # Verifica se já existe arquivo de saída (agora .md)
            nome_base = arquivo_pdf.stem
            arquivo_md = pasta_destino_arquivo / f"{nome_base}.md"
            
            if arquivo_md.exists() and not self.sobrescrever:
                self._adicionar_log(f"  -> IGNORADO: {arquivo_md.name} já existe")
                self.total_ignorados += 1
                continue
            
            # Extrai o texto
            try:
                # Calcula pasta de log mantendo estrutura de subpastas se houver
                if self.pasta_log != self.pasta_destino:
                    try:
                        caminho_relativo = arquivo_pdf.parent.relative_to(self.pasta_origem)
                        pasta_log_arquivo = self.pasta_log / caminho_relativo
                    except ValueError:
                        pasta_log_arquivo = self.pasta_log
                else:
                    pasta_log_arquivo = pasta_destino_arquivo
                
                extrator = ExtrairPdf(
                    str(arquivo_pdf), 
                    str(pasta_destino_arquivo),
                    pasta_log=str(pasta_log_arquivo),
                    ignorar_dependencias=self.ignorar_dependencias,
                    gerar_dicas=False  # Já gerado na pasta principal
                )
                sucesso = extrator.extrair()
                
                self.total_processados += 1
                if sucesso:
                    self.total_sucesso += 1
                    self._adicionar_log(f"  -> SUCESSO: {arquivo_md.name}")
                else:
                    self.total_falha += 1
                    self._adicionar_log(f"  -> FALHA: Verifique {nome_base}.log")
                    
            except Exception as e:
                self.total_processados += 1
                self.total_falha += 1
                self._adicionar_log(f"  -> ERRO: {str(e)}")
        
        # Resumo final
        self._adicionar_log("\n" + "=" * 60)
        self._adicionar_log("RESUMO DO PROCESSAMENTO")
        self._adicionar_log("=" * 60)
        self._adicionar_log(f"Total de arquivos encontrados: {len(arquivos)}")
        self._adicionar_log(f"Processados com sucesso: {self.total_sucesso}")
        self._adicionar_log(f"Processados com falha: {self.total_falha}")
        self._adicionar_log(f"Ignorados (já existem): {self.total_ignorados}")
        self._adicionar_log("=" * 60)
        
        self._salvar_log()
        return self._gerar_estatisticas()
    
    def _gerar_estatisticas(self) -> dict:
        """Gera dicionário com estatísticas do processamento."""
        return {
            'processados': self.total_processados,
            'sucesso': self.total_sucesso,
            'falha': self.total_falha,
            'ignorados': self.total_ignorados
        }


def criar_yaml_modelo(caminho: str):
    """Cria um arquivo YAML modelo no caminho especificado."""
    conteudo = '''# Configuração para extração em lote de PDFs
# Execute com: python extrair_pdf.py config_extracao.yaml

# Pasta contendo os arquivos PDF (obrigatório)
pasta_origem: ./pdfs

# Pasta para salvar os arquivos extraídos (se vazio, usa pasta_origem)
pasta_destino: ./textos

# Pasta para salvar os logs (se vazio, usa pasta_destino)
# pasta_log: ./logs

# Processar subpastas recursivamente? (padrão: true)
subpastas: true

# Sobrescrever arquivos existentes? (padrão: false)
sobrescrever: false

# Ignorar erros de dependências opcionais (libGL, tesseract)?
# Se true: continua a extração sem OCR/detecção de tabelas, registra avisos no log
# Se false: interrompe a execução com erro se dependências estiverem faltando
# (padrão: true)
ignorar_dependencias: true
'''
    
    with open(caminho, 'w', encoding='utf-8') as f:
        f.write(conteudo)
    
    print(f"✅ Arquivo modelo criado: {caminho}")


def mostrar_uso():
    """Mostra instruções de uso do script."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                   EXTRATOR DE PDF PARA MARKDOWN - DOCLING                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ Uso:                                                                         ║
║   python extrair_pdf.py <arquivo_pdf>                                        ║
║   python extrair_pdf.py <arquivo_yaml>                                       ║
║                                                                              ║
║ Exemplos:                                                                    ║
║   python extrair_pdf.py documento.pdf                                        ║
║   python extrair_pdf.py config_extracao.yaml                                 ║
║                                                                              ║
║ Formato do arquivo YAML:                                                     ║
║   pasta_origem: ./pdfs                                                       ║
║   pasta_destino: ./textos                                                    ║
║   pasta_log: ./logs                                                          ║
║   subpastas: true                                                            ║
║   sobrescrever: false                                                        ║
║   ignorar_dependencias: true                                                 ║
║                                                                              ║
║ Parâmetros YAML:                                                             ║
║   - pasta_origem: Pasta contendo os PDFs (obrigatório)                       ║
║   - pasta_destino: Pasta para salvar os textos (padrão: pasta_origem)        ║
║   - pasta_log: Pasta para salvar os logs (padrão: pasta_destino)             ║
║   - subpastas: True/False - processar subpastas (padrão: True)               ║
║   - sobrescrever: True/False - sobrescrever existentes (padrão: False)       ║
║   - ignorar_dependencias: True/False - ignorar deps opcionais (padrão: True) ║
║                                                                              ║
║ Saída:                                                                       ║
║   - Arquivo .md com o texto em Markdown (tags <PAGINA:nnn> e <IMAGEM:nnn>)   ║
║   - Arquivo .log com detalhes da extração de cada arquivo                    ║
║   - log_extração.txt com resumo geral (modo pasta)                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")


if __name__ == '__main__':
    # Verifica se o docling está instalado
    if not DOCLING_DISPONIVEL:
        print("❌ ERRO: O pacote 'docling' não está instalado.")
        print("   Instale com: pip install docling")
        sys.exit(1)
    
    if len(sys.argv) < 2:
        mostrar_uso()
        sys.exit(1)
    
    arquivo_enviado = sys.argv[1]
    
    # Processa arquivo PDF individual
    if os.path.isfile(arquivo_enviado) and arquivo_enviado.lower().endswith('.pdf'):
        print(f"\n🔄 Processando PDF: {arquivo_enviado}\n")
        extrator = ExtrairPdf(arquivo_enviado)
        sucesso = extrator.extrair()
        
        if sucesso:
            print(f"\n✅ Markdown extraído com sucesso!")
            print(f"   Arquivo: {extrator.arquivo_md}")
        else:
            print(f"\n❌ Falha na extração. Verifique o log: {extrator.arquivo_log}")
            sys.exit(1)
    
    # Processa arquivo YAML com configurações
    elif arquivo_enviado.lower().endswith('.yaml') or arquivo_enviado.lower().endswith('.yml'):
        # Verifica se o arquivo existe
        if not os.path.isfile(arquivo_enviado):
            print(f"\n⚠️  Arquivo YAML não encontrado: {arquivo_enviado}")
            resposta = input("   Deseja criar um arquivo modelo? (s/n): ").strip().lower()
            
            if resposta in ['s', 'sim', 'y', 'yes']:
                criar_yaml_modelo(arquivo_enviado)
                print(f"\n📝 Edite o arquivo '{arquivo_enviado}' e execute novamente.")
            else:
                print("   Operação cancelada.")
            sys.exit(0)
        
        print(f"\n🔄 Processando pasta com configuração: {arquivo_enviado}\n")
        processador = ProcessarPasta(arquivo_enviado)
        estatisticas = processador.processar()
        
        print(f"\n📊 Resultado:")
        print(f"   Sucesso: {estatisticas['sucesso']}")
        print(f"   Falhas: {estatisticas['falha']}")
        print(f"   Ignorados: {estatisticas['ignorados']}")
        
        if estatisticas['falha'] > 0:
            sys.exit(1)
    
    else:
        print(f"\n❌ Arquivo não encontrado ou formato inválido: {arquivo_enviado}")
        print("   Use arquivos .pdf ou .yaml")
        mostrar_uso()
        sys.exit(1)