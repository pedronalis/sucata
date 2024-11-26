import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image, ImageDraw, ImageFont, ImageTk
import pysubs2
import threading
import torch
import transformers
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from accelerate import init_empty_weights, infer_auto_device_map, load_checkpoint_and_dispatch
import re
from pymkv import MKVFile
import os
import subprocess


def extrair_legenda_mkv(arquivo_mkv, caminho_saida, faixa_id):
    """
    Extrai a faixa de legenda especificada de um arquivo MKV usando o mkvextract.
    """
    try:
        # Define o caminho para o arquivo de saída
        nome_legenda = os.path.join(caminho_saida, f"legenda_{faixa_id}.ass")  # Assume o formato .ass com base no output

        # Comando para extrair a faixa de legenda
        comando_extrair = [
            "mkvextract",
            "tracks",
            arquivo_mkv,
            f"{faixa_id}:{nome_legenda}"
        ]

        # Executa o comando de extração
        resultado = subprocess.run(comando_extrair, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Verifica o retorno do comando
        if resultado.returncode != 0:
            raise Exception(f"Erro ao executar mkvextract: {resultado.stderr}")

        print(f"Legenda extraída com sucesso: {nome_legenda}")
        return nome_legenda
    except Exception as e:
        print(f"Erro ao extrair legenda: {e}")
        return None


import subprocess

def obter_faixas_legenda(arquivo_mkv):
    """
    Obtém as faixas de legenda disponíveis em um arquivo MKV usando o mkvmerge.
    """
    try:
        comando = ["mkvmerge", "-i", arquivo_mkv]
        resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if resultado.returncode != 0:
            raise Exception(f"Erro ao executar mkvmerge: {resultado.stderr}")

        faixas_legenda = []
        for linha in resultado.stdout.splitlines():
            if "subtitles" in linha:
                partes = linha.split(":")
                faixa_id = int(partes[0].split()[-1])
                detalhes = partes[1].strip()
                
                # Tentativa de extrair idioma, se disponível
                idioma = "Desconhecido"
                if "(" in detalhes and ")" in detalhes:
                    parenteses = detalhes.split("(")[-1].split(")")[0]
                    if len(parenteses) == 3:  # ISO 639-2 format (e.g., "eng", "por")
                        idioma = parenteses
                
                nome = detalhes.replace(f"({idioma})", "").strip() if idioma != "Desconhecido" else detalhes
                faixas_legenda.append({"id": faixa_id, "idioma": idioma, "nome": nome})
        return faixas_legenda
    except Exception as e:
        print(f"Erro ao obter faixas de legenda: {e}")
        return []


def selecionar_faixa_legenda(faixas_legenda, callback, root):
    """
    Exibe uma janela modal para o usuário selecionar uma faixa de legenda.
    Após a seleção, chama o callback com o ID da faixa selecionada.
    """
    faixa_selecionada = tk.StringVar()

    def confirmar_selecao():
        selecionado = lista_faixas.curselection()
        if not selecionado:
            tk.messagebox.showwarning("Aviso", "Nenhuma faixa foi selecionada.", parent=janela_selecao)
            return
        faixa = faixas_legenda[selecionado[0]]  # Acessa o dicionário da faixa selecionada
        faixa_selecionada.set(faixa["id"])  # Retorna o ID da faixa
        janela_selecao.destroy()  # Fecha a janela após seleção

    # Janela secundária para exibir as opções
    janela_selecao = tk.Toplevel(root)
    janela_selecao.title("Selecione uma Faixa")
    janela_selecao.geometry("400x300")
    janela_selecao.iconbitmap("img/sucata_icon.ico")
    janela_selecao.configure(bg="#181825")
    janela_selecao.transient(root)  # Define como janela modal
    janela_selecao.grab_set()

    label = tk.Label(
        janela_selecao, text="Selecione a faixa de legenda para traduzir:", bg="#181825", fg="white"
    )
    label.pack(pady=10)

    lista_faixas = tk.Listbox(
        janela_selecao, bg="#202030", fg="#14b83e", height=10, width=50, selectmode=tk.SINGLE
    )
    for faixa in faixas_legenda:
        lista_faixas.insert(
            tk.END,
            f"Faixa {faixa['id']} - {faixa['idioma']} ({faixa['nome']})",
        )
    lista_faixas.pack(pady=10)

    btn_confirmar = tk.Button(
        janela_selecao, text="Confirmar", command=confirmar_selecao, bg="#1E1E2A", fg="white"
    )
    btn_confirmar.pack(pady=10)

    janela_selecao.wait_window()

    if faixa_selecionada.get():
        callback(faixa_selecionada.get())  # Chama o callback com o ID da faixa selecionada
    else:
        callback(None)  # Nenhuma faixa foi selecionada


def remover_formatacao_legenda(eventos):
    def limpar_texto(texto):
        texto = re.sub(r"\{.*?\}", "", texto)
        texto = re.sub(r"<.*?>", "", texto)
        return texto.strip()

    for evento in eventos:
        evento.text = limpar_texto(evento.text)
    return eventos


def limpar_texto_traduzido(texto_traduzido):
    """
    Remove os delimitadores e qualquer conteúdo adicional que não faça parte do texto traduzido.
    """
    # Verifica se os delimitadores estão presentes
    if "<<<Texto a ser traduzido>>>" in texto_traduzido:
        # Extrai o texto entre os delimitadores
        texto_traduzido = texto_traduzido.split("<<<Texto a ser traduzido>>>")[1]
        texto_traduzido = texto_traduzido.split("<<<Fim do texto>>>")[0]

    return texto_traduzido.strip()


def inicializar_pipeline(model_id="meta-llama/Meta-Llama-3.1-8B-Instruct"):
    try:
        print("Carregando pipeline com bfloat16 e device map automático...")
        pipeline = transformers.pipeline(
            "text-generation",
            model=model_id,
            model_kwargs={"torch_dtype": torch.bfloat16},
            device_map="auto",
        )
        print("Pipeline carregado com sucesso.")
        return pipeline
    except Exception as e:
        print(f"Erro ao carregar pipeline: {e}")
        raise


def traduzir_eventos(eventos, pipeline, idioma_origem, idioma_destino, log_text, barra_progresso=None):
    traducoes = []
    if barra_progresso:
        barra_progresso["maximum"] = len(eventos)

    for i, evento in enumerate(eventos):
        # Contexto: 5 linhas antes e 5 depois
        contexto_anterior = " ".join([e.text for e in eventos[max(0, i-4):i]])
        contexto_posterior = " ".join([e.text for e in eventos[i+1:min(len(eventos), i+5)]])

        # Construção do prompt com delimitadores claros
        prompt_content = []
        if contexto_anterior:
            prompt_content.append(f"[Contexto anterior]: {contexto_anterior}")
        prompt_content.append(f"[Texto a ser traduzido]: {evento.text}")
        if contexto_posterior:
            prompt_content.append(f"[Contexto posterior]: {contexto_posterior}")
       
        prompt = [
            {"role": "system", "content": (
                f"Você é um tradutor profissional especializado em legendas para filmes, séries e animes. "
                f"Traduza do {idioma_origem} para o {idioma_destino} seguindo estas diretrizes:\n"
                "- Preserve o tom, estilo e naturalidade do idioma original; adapte trechos para melhor coesão no {idioma_destino}.\n"
                "- Adapte expressões, gírias e referências culturais com equivalência cultural, garantindo clareza ao público do {idioma_destino}.\n"
                "- Antes de traduzir, analise o contexto emocional do texto e adapte o vocabulário para transmitir o mesmo impacto.\n"
                "- Evite traduções literais que causem ambiguidades; reorganize frases para garantir fluidez e clareza.\n"
                "- Use uma linguagem fluida, acessível e consistente, evitando redundâncias ou exageros.\n"
                r"- Preserve a formatação original (espaçamentos '  ', quebras '\\N', estilos como {{\pos}}, {{\an}}, etc.).\n"                
                "- Analise os tempos verbais com cuidado; traduza 'ser' e 'estar' conforme características permanentes ou temporárias.\n"
                "- Garanta consistência na terminologia ao longo da tradução, criando um glossário interno se necessário.\n"
                "- Reorganize as frases para garantir fluidez e clareza, sem comprometer o sentido original.\n"
                "- A tradução deve ser clara, objetiva e concisa; evite textos truncados ou longos.\n"
                "- Ajuste a terminologia de maneira consistente em todas as legendas, consultando o contexto geral do texto.\n"
                "- Ao traduzir diálogos emocionais, capture o tom apropriado da cena, adaptando expressões e vocabulário.\n"
                "- Garanta que o texto traduzido mantenha o alinhamento visual e respeite o layout do original.\n"
                "- A tradução precisa ser estritamente apenas o texto indicado traduzido, sem observações, conteúdos extras ou antecipação de contextos.\n"
                "- Considere os contextos para executar a tradução:\n\n"
                f"[Contexto anterior]: {contexto_anterior}\n"
                f"[Contexto posterior]: {contexto_posterior}\n"
            )},
            {"role": "user", "content": f"Traduza apenas o texto a seguir, seguindo rigorosamente todas as diretrizes: {evento.text}"}
        ]


        try:
            # Gera a tradução usando o pipeline
            output = pipeline(prompt, max_new_tokens=1024)
            print(f"Saída do pipeline para o evento {i + 1}: {output}")  # Debugging

             # Extrair a tradução do objeto gerado
            if isinstance(output, list):
                mensagens = output[0].get("generated_text", [])
                if isinstance(mensagens, list):
                    for mensagem in mensagens:
                        if mensagem.get("role") == "assistant":
                            texto_traduzido = mensagem.get("content", "").strip()
                            texto_traduzido = limpar_texto_traduzido(texto_traduzido)  # Limpa os delimitadores
                            traducoes.append(texto_traduzido)
                            break
                    else:
                        raise ValueError("Nenhuma mensagem com 'role': 'assistant' encontrada.")
                else:
                    raise ValueError("Formato inesperado em 'generated_text'.")
            else:
                raise ValueError(f"Formato inesperado de saída: {output}")
        except Exception as e:
            log_text.insert(tk.END, f"Erro ao traduzir evento {i + 1}: {e}\n")
            traducoes.append(evento.text)  # Mantém o texto original em caso de erro

        # Atualizar barra de progresso e logs
        if barra_progresso:
            barra_progresso["value"] += 1
            barra_progresso.update()

        if log_text and i % 10 == 0:
            log_text.insert(tk.END, f"Traduzido {i + 1}/{len(eventos)} linhas...\n")
            log_text.see(tk.END)
            log_text.update()

    return traducoes


def salvar_legenda(subs, arquivo_saida):
    try:
        subs.save(arquivo_saida)
        print(f"Legenda traduzida salva em: {arquivo_saida}")
    except Exception as e:
        print(f"Erro ao salvar legenda: {e}")


def processar_legenda(arquivo_legenda, idioma_origem, idioma_destino, log_text, barra_progresso, pipeline):
    try:
        print(f"Processando o arquivo: {arquivo_legenda}")  # Log para verificar o arquivo
        subs = pysubs2.load(arquivo_legenda)  # Carrega a legenda
        print(f"Número de eventos carregados: {len(subs)}")  # Verifica se os eventos foram carregados
        if arquivo_legenda.endswith(".srt"):
            # Limpeza de formatação
            eventos = remover_formatacao_legenda([event for event in subs if event.text.strip()])
        elif arquivo_legenda.endswith(".ass") or arquivo_legenda.endswith(".ssa"):
            eventos = [event for event in subs if event.text.strip()]
        else:
            raise ValueError("Formato de legenda não suportado.")

        # Traduz eventos
        traducoes = traduzir_eventos(eventos, pipeline, idioma_origem, idioma_destino, log_text, barra_progresso)

        for evento, traducao in zip(eventos, traducoes):
            evento.text = traducao

        # Salva a legenda traduzida
        subs.save(arquivo_legenda.replace(".srt", "_traduzido.srt").replace(".ass", "_traduzido.ass").replace(".ssa", "_traduzido.ssa"))
        print(f"Legenda traduzida salva com sucesso.")
        return arquivo_legenda.replace(".srt", "_traduzido.srt").replace(".ass", "_traduzido.ass").replace(".ssa", "_traduzido.ssa")
    except Exception as e:
        print(f"Erro ao processar a legenda: {e}")
        return None
    

def processar_arquivo(arquivo, idioma_origem, idioma_destino, log_text, barra_progresso):
    if arquivo.endswith(".mkv"):
        # Lidar com arquivos MKV
        caminho_saida = os.path.dirname(arquivo)
        legenda_extraida = extrair_legenda_mkv(arquivo, caminho_saida)
        if legenda_extraida:
            legenda_traduzida = processar_legenda(legenda_extraida, idioma_origem, idioma_destino, log_text, barra_progresso)
            if legenda_traduzida and (legenda_traduzida.endswith(".ass") or legenda_traduzida.endswith(".ssa")):
                saida_mkv = os.path.join(caminho_saida, "output_traduzido.mkv")
                reembutir_legenda_mkv(arquivo, legenda_traduzida, saida_mkv)
                log_text.insert(tk.END, f"Processamento concluído. Arquivo MKV salvo em: {saida_mkv}\n")
            else:
                log_text.insert(tk.END, "Legenda SRT traduzida salva separadamente.\n")
        else:
            log_text.insert(tk.END, "Nenhuma legenda extraída do arquivo MKV.\n")
    elif arquivo.endswith((".srt", ".ass", ".ssa")):
        # Lidar com arquivos de legenda diretamente
        legenda_traduzida = processar_legenda(arquivo, idioma_origem, idioma_destino, log_text, barra_progresso)
        if legenda_traduzida:
            log_text.insert(tk.END, f"Legenda traduzida salva em: {legenda_traduzida}\n")
        else:
            log_text.insert(tk.END, "Erro ao processar a legenda.\n")
    else:
        log_text.insert(tk.END, "Formato de arquivo não suportado.\n")


def reembutir_legenda_mkv(arquivo_mkv, legenda_traduzida, saida_mkv):
    try:
        mkv = MKVFile(arquivo_mkv)
        mkv.add_track(legenda_traduzida)
        mkv.mux(saida_mkv)
        print(f"Arquivo MKV com legenda traduzida salvo como: {saida_mkv}")
    except Exception as e:
        print(f"Erro ao reembutir a legenda: {e}")


def iniciar_interface():
        # Inicializar o pipeline globalmente
    pipeline = None  # Inicialize como None para verificar erros de carregamento

    try:
        pipeline = inicializar_pipeline()
    except Exception as e:
        print(f"Erro ao inicializar o pipeline: {e}")
    
    def carregar_arquivo():
        arquivo = filedialog.askopenfilename(
            filetypes=[("Arquivos de Legenda e MKV", "*.srt *.ass *.ssa *.mkv"),]
        )
        entrada_arquivo.delete(0, tk.END)
        entrada_arquivo.insert(0, arquivo)

    def iniciar_processamento():
    # Função de processamento em uma thread separada
        def tarefa():
            try:
                # Desativa o botão enquanto processa
                btn_iniciar.config(state=tk.DISABLED)
                barra_progresso.config(mode="indeterminate")
                barra_progresso.start()
                carregando_label.config(text="Processando...")

                # Recupera os valores da interface
                arquivo = entrada_arquivo.get()
                idioma_origem = dropdown_idioma_origem.get().split(" - ")[0] if dropdown_idioma_origem.get() else None
                idioma_destino = "Português do Brasil"

                if not arquivo:
                    log_text.insert(tk.END, "Por favor, selecione um arquivo.\n")
                    return
                if not idioma_origem:
                    log_text.insert(tk.END, "Por favor, selecione o idioma de origem.\n")
                    return

                # Decide o que fazer com base no tipo de arquivo
                if arquivo.endswith(".mkv"):
                    def processar_faixa(faixa_selecionada):
                        if faixa_selecionada:
                            faixa_id = int(faixa_selecionada)
                            caminho_saida = os.path.dirname(arquivo)
                            legenda_extraida = extrair_legenda_mkv(arquivo, caminho_saida, faixa_id)
                            if legenda_extraida:
                                legenda_traduzida = processar_legenda(legenda_extraida, idioma_origem, idioma_destino, log_text, barra_progresso, pipeline)
                                if legenda_traduzida:
                                    saida_mkv = os.path.join(caminho_saida, "output_traduzido.mkv")
                                    reembutir_legenda_mkv(arquivo, legenda_traduzida, saida_mkv)
                                    log_text.insert(tk.END, f"Processamento concluído. Arquivo MKV salvo em: {saida_mkv}\n")
                                else:
                                    log_text.insert(tk.END, "Erro ao processar a legenda.\n")
                            else:
                                log_text.insert(tk.END, "Erro ao extrair a legenda selecionada.\n")
                        else:
                            log_text.insert(tk.END, "Nenhuma faixa foi selecionada.\n")

                    faixas_legenda = obter_faixas_legenda(arquivo)
                    if faixas_legenda:
                        selecionar_faixa_legenda(faixas_legenda, processar_faixa, root=janela)
                    else:
                        log_text.insert(tk.END, "Nenhuma faixa de legenda encontrada no arquivo MKV.\n")

                elif arquivo.endswith((".srt", ".ass", ".ssa")):
                    # Processa arquivos de legenda diretamente
                    log_text.insert(tk.END, "Processando legenda...\n")
                    legenda_traduzida = processar_legenda(arquivo, idioma_origem, idioma_destino, log_text, barra_progresso, pipeline)
                    if legenda_traduzida:
                        log_text.insert(tk.END, f"Legenda traduzida salva em: {legenda_traduzida}\n")
                    else:
                        log_text.insert(tk.END, "Erro ao processar a legenda.\n")
                else:
                    log_text.insert(tk.END, "Formato de arquivo não suportado.\n")

            except Exception as e:
                log_text.insert(tk.END, f"Erro durante o processamento: {e}\n")
            finally:
                # Reativa o botão e para a barra de progresso
                btn_iniciar.config(state=tk.NORMAL)
                barra_progresso.stop()
                barra_progresso.config(mode="determinate")
                carregando_label.config(text="")

        # Cria e inicia a thread
        thread = threading.Thread(target=tarefa)
        thread.start()



    janela = tk.Tk()
    janela.title("Sucata")
    janela.geometry("400x750")
    janela.configure(bg="#181825")
    janela.iconbitmap("img/sucata_icon.ico")

    fonteTitulo = ImageFont.truetype("fonts/Horizon.otf", size=24)
    fonteSubTitulo = ImageFont.truetype("fonts/FKGroteskNeueTrial-Bold.otf", size=18)

    def criar_texto_imagem(texto, largura, altura, fonte, cor_fundo, cor_texto):
        """Cria uma imagem com texto estilizado usando Pillow."""
        img = Image.new("RGBA", (largura, altura), color=cor_fundo)
        draw = ImageDraw.Draw(img)
        # Obter o tamanho do texto usando textbbox
        bbox = draw.textbbox((0, 0), texto, font=fonte)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        # Centralizar o texto na imagem
        draw.text(((largura - w) // 2, (altura - h) // 2), texto, font=fonte, fill=cor_texto)
        return ImageTk.PhotoImage(img)

    imagem = Image.open("img/sucata_hello.png")
    imagem = imagem.resize((150, 150))  # Redimensionar, se necessário
    imagem_tk = ImageTk.PhotoImage(imagem)
    img_label = tk.Label(janela, image=imagem_tk, bg="#181825")
    img_label.image = imagem_tk  # Referência da imagem
    img_label.pack(pady=(20, 0))

    # Título
    titulo_img = criar_texto_imagem(
        "Olá, sou o Sucata.",
        400,
        30,
        fonteTitulo,
        cor_fundo="#181825",
        cor_texto="white",
    )
    title_label = tk.Label(janela, image=titulo_img, bg="#181825")
    title_label.image = titulo_img
    title_label.pack(pady=(5, 7))

    # Subtítulo
    subtitulo_img = criar_texto_imagem(
        "Sou um tradutor de legendas\nusando Inteligência Artificial.",
        400,
        70,
        fonteSubTitulo,
        cor_fundo="#181825",
        cor_texto="white",
    )
    subTitle_label = tk.Label(janela, image=subtitulo_img, bg="#181825")
    subTitle_label.image = subtitulo_img
    subTitle_label.pack(pady=(0,5))



    lbl_arquivo = tk.Label(janela, text="Insira um arquivo de legenda:", bg="#181825", fg="white")
    lbl_arquivo.pack()
    entrada_arquivo = tk.Entry(janela, width=50)
    entrada_arquivo.pack()
    btn_carregar = tk.Button(janela, text="Selecionar Arquivo", command=carregar_arquivo, bg="#1E1E2A", fg="white")
    btn_carregar.pack(pady=10)

    lbl_idioma_origem = tk.Label(janela, text="Idioma de Origem:", bg="#181825", fg="white")
    lbl_idioma_origem.pack()
    idiomas_disponiveis = [
        "en - Inglês",
        "es - Espanhol",
        "fr - Francês",
        "de - Alemão",
        "it - Italiano",
        "ja - Japonês",
        "ko - Coreano",
        "zh - Chinês",
        "ru - Russo",
        "ar - Árabe",
    ]
    dropdown_idioma_origem = ttk.Combobox(janela, values=idiomas_disponiveis, width=15)
    dropdown_idioma_origem.pack(pady=(0, 10))
    dropdown_idioma_origem.set("en - Inglês")

    btn_iniciar = tk.Button(janela, text="Iniciar Tradução", command=iniciar_processamento, bg="#1E1E2A", fg="white")
    btn_iniciar.pack()

    barra_progresso = ttk.Progressbar(janela, length=400, mode="determinate")
    barra_progresso.pack(pady=10)

    carregando_label = tk.Label(janela, text="", bg="#181825", fg="white")
    carregando_label.pack()

    log_text = tk.Text(janela, height=10, wrap="word", bg="#202030", fg="#14b83e", insertbackground="white")
    log_text.pack()

    footer_label = tk.Label(janela, text="Desenvolvido com ❤️\npor Pedro Guina Saltareli.", font=("Courier New", 10), fg="white", bg="#181825")
    footer_label.pack(pady=5)

    janela.mainloop()


if __name__ == "__main__":
    iniciar_interface()
