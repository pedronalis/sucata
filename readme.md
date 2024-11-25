<p align="center">
    <img src="./img/sucata_icon.ico" align="center" width="30%">
</p>
<p align="center"><h1 align="center">Olá, eu sou o SUCATA</h1></p>
<p align="center">
	<em>Um tradutor de legendas que usa modelos de Inteligência Artificias open-source.</em>
</p>
<p align="center">
	<!-- local repository, no metadata badges. --></p>
<p align="center">Desenvolvido em:</p>
<p align="center">
	<img src="https://img.shields.io/badge/Python-3776AB.svg?style=default&logo=Python&logoColor=white" alt="Python">
</p>
<br>

##  Table of Contents

- [ Overview](#-overview)
- [ Features](#-features)
- [ Project Structure](#-project-structure)
- [ Getting Started](#-getting-started)
  - [ Prerequisites](#-prerequisites)
  - [ Installation](#-installation)
  - [ Usage](#-usage)
  - [ Testing](#-testing)
- [ Project Roadmap](#-project-roadmap)
- [ Contributing](#-contributing)
- [ License](#-license)
- [ Acknowledgments](#-acknowledgments)

---

##  Overview

Sucata é uma ferramenta de código aberto que extrai e traduz legendas de arquivos MKV, oferecendo uma interface amigável para seleção de arquivos e trilhas. Além de também traduzir legendas .srt, .ass e .ssa.

Utilizando um prompt extremamente refinado para que a legenda possa ter a melhor qualidade possível.

---

##  Features

| **Scalability** |                  |
| :---:           | :---          |
| 📈 Fato sobre Escalabilidade 1: A arquitetura baseada em microsserviços permite escalabilidade horizontal ao distribuir as requisições entre várias instâncias de cada serviço. |
| 📈 📈 Fato sobre Escalabilidade 2: O balanceamento de carga é distribuído, otimizando a utilização de recursos e garantindo o processamento eficiente do tráfego recebido. |
| 📈 Fato sobre Escalabilidade 3: A consistência dos dados é mantida por meio de APIs padronizadas e filas de mensagens, reduzindo o risco de inconsistências. |

---

##  Project Structure

```sh
└── sucata/
    ├── app.py
    ├── fonts
    │   ├── FKGroteskNeueTrial-Bold.otf
    │   ├── FKGroteskNeueTrial-Regular.otf
    │   └── Horizon.otf
    ├── img
    │   ├── sucata_hello.png
    │   └── sucata_icon.ico
    └── requirements.txt
```


###  Project Index
<details open>
	<summary><b><code>SUCATA/</code></b></summary>
	<details> <!-- __root__ Submodule -->
		<summary><b>Root</b></summary>
		<blockquote>
			<table>
			<tr>
				<td><b><a href='Desktop/sucata/app.py'>app.py</a></b></td>
				<td>- **Sumário:**

O arquivo `app.py` serve como o ponto de entrada principal para uma aplicação que extrai legendas de arquivos MKV utilizando a biblioteca `pysubs2`.<br>  
- O código realiza essa tarefa por meio de uma interface gráfica (GUI) construída com Tkinter, permitindo que os usuários selecionem um arquivo MKV e especifiquem a faixa de legenda desejada.<br>  
- Ao ser executado, a aplicação combina ferramentas de linha de comando (como o `mkvextract`) com modelos de aprendizado de máquina (via PyTorch e Transformers) para extrair a faixa de legenda especificada do arquivo MKV selecionado.  

**Key Functionality:**

- Oferece uma interface amigável para selecionar um arquivo MKV e especificar a faixa de legenda desejada.
- Utiliza o pysubs2 para extrair a faixa de legenda especificada do arquivo MKV selecionado.
- Emprega modelos de aprendizado de máquina (via PyTorch e Transformers) para aumentar a precisão na extração de legendas.


##  Getting Started

###  Prerequisites

Antes de começar a usar o Sucata, certifique-se de que o ambiente de execução atenda aos seguintes requisitos:

- **Linguagem de Programação:** Python (nível básico recomendado)
- **Gerenciador de Pacotes:** Pip


###  Installation

Siga o passo a passo para instalar o sucata

**Build from source:**

1. Clone o repositório do Sucata:
```sh
❯ git clone https://github.com/pedronalis/sucata
```

2. Entre no diretório:
```sh
❯ cd sucata
```

3. Instale as dependências:


**Use `pip`** &nbsp; [<img align="center" src="" />]()

```sh
❯ echo 'pip install -r requirements.txt'
```




###  Usage
Rode o Sucata utilizando o comando:
**Using `pip`** &nbsp; [<img align="center" src="" />]()

```sh
❯ echo 'python app.py'
```


###  Testing
Run the test suite using the following command:
**Using `pip`** &nbsp; [<img align="center" src="" />]()

```sh
❯ echo 'INSERT-TEST-COMMAND-HERE'
```


---
##  Project Roadmap

- [X] **`Task 1`**: <strike>Implement feature one.</strike>
- [ ] **`Task 2`**: Implement feature two.
- [ ] **`Task 3`**: Implement feature three.

---

##  Contributing

- **💬 [Join the Discussions](https://LOCAL/Desktop/sucata/discussions)**: Share your insights, provide feedback, or ask questions.
- **🐛 [Report Issues](https://LOCAL/Desktop/sucata/issues)**: Submit bugs found or log feature requests for the `sucata` project.
- **💡 [Submit Pull Requests](https://LOCAL/Desktop/sucata/blob/main/CONTRIBUTING.md)**: Review open PRs, and submit your own PRs.

<details closed>
<summary>Contributing Guidelines</summary>

1. **Fork the Repository**: Start by forking the project repository to your LOCAL account.
2. **Clone Locally**: Clone the forked repository to your local machine using a git client.
   ```sh
   git clone C:\Users\Pedro\Desktop\sucata
   ```
3. **Create a New Branch**: Always work on a new branch, giving it a descriptive name.
   ```sh
   git checkout -b new-feature-x
   ```
4. **Make Your Changes**: Develop and test your changes locally.
5. **Commit Your Changes**: Commit with a clear message describing your updates.
   ```sh
   git commit -m 'Implemented new feature x.'
   ```
6. **Push to LOCAL**: Push the changes to your forked repository.
   ```sh
   git push origin new-feature-x
   ```
7. **Submit a Pull Request**: Create a PR against the original project repository. Clearly describe the changes and their motivations.
8. **Review**: Once your PR is reviewed and approved, it will be merged into the main branch. Congratulations on your contribution!
</details>

<details closed>
<summary>Contributor Graph</summary>
<br>
<p align="left">
   <a href="https://LOCAL{/Desktop/sucata/}graphs/contributors">
      <img src="https://contrib.rocks/image?repo=Desktop/sucata">
   </a>
</p>
</details>

---

##  License

This project is protected under the [SELECT-A-LICENSE](https://choosealicense.com/licenses) License. For more details, refer to the [LICENSE](https://choosealicense.com/licenses/) file.

---

##  Acknowledgments

- List any resources, contributors, inspiration, etc. here.

---
