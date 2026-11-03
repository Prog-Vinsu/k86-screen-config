# Attack Shark K86 Screen Uploader (Linux)

[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)](LICENSE)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-orange.svg)](#requisitos)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](#requisitos)

> Utilitário gráfico e de linha de comando para envio de **GIFs animados** e imagens estáticas para a telinha TFT (240×135) do teclado mecânico **Attack Shark K86** no Linux, sem depender de Windows, Wine ou máquinas virtuais.

[English version available (README.md)](README.md)

---

## ⚡ Recursos

* **Janela Desktop Nativa (GTK 3 + WebKit2GTK):** Aplicativo gráfico executado no ambiente de trabalho nativo com suporte a **Arrastar & Soltar (Drag & Drop)**.
* **Comunicação Direta por IPC (Sem Servidor HTTP):** Elimina portas HTTP locais e riscos de CORS; a troca de dados ocorre via ponte de memória de processo isolada.
* **Verificação de Segurança de Hardware:** Consulta o identificador do aparelho via comando de leitura `0x8F` antes de enviar qualquer pacote, garantindo que apenas teclados Attack Shark K86 verificados recebam gravações.
* **Telinha TFT & Envio de GIFs:**
  * Pré-visualização com moldura 240×135 em tempo real.
  * Slider de velocidade/delay entre quadros.
  * Amostragem inteligente de quadros para respeitar a memória flash.
  * Modos de corte: Preencher cortando sobras (*Crop* - padrão), Conter (*Contain*) ou Esticar (*Stretch*).
* **Configurações de Teclado (Compatível com sharkfin):**
  * **Sincronização de Relógio:** Sincroniza o relógio da telinha com o horário do PC em um clique.
  * **Debounce de Teclas:** Ajuste de latência de 1ms a 10ms.
  * **Interruptores de Hardware:** Win Lock, inversão WASD/Setas, desligar LEDs principais, desligar LEDs laterais.
  * **Temporizadores de Suspensão:** Configuração independente de economia de bateria para 2.4 GHz e Bluetooth.
* **Controle de Iluminação RGB Principal:**
  * 18 modos e efeitos de animação (Estático, Respiração, Onda, Ondulação, Meteoro, etc.).
  * Rodinha de cores HSV interativa + 14 atalhos de cores rápidas ou modo Arco-íris dinâmico.
  * Controle de brilho (0 a 4) e velocidade da animação (0 a 4).
* **Iluminação RGB das Barras Laterais (Side LEDs - SLEDPARAM):**
  * Controle dedicado das faixas de LED nas bordas do K86.
  * 6 modos laterais: Desligado, Estático, Respiração, Neon, Onda e Cobra.
  * Ajustes dedicados de velocidade, brilho e sincronização com a cor principal.
* **Restauração de Fábrica:** Comando para redefinir as configurações internas para o padrão de fábrica.
* **Modo CLI Integrado:** Execute sem argumentos para a janela gráfica ou passe o caminho do arquivo diretamente pelo terminal.
* **Modo de Simulação (Dry-Run):** Testa conversão e comunicação com o hardware sem gravar na flash (`--dry-run`).

---

## 🖥️ Compatibilidade

| Modelo | USB VID:PID | Device ID (`0x8F`) | Linha da Controladora | Suporte de Tela |
|---|---|---|---|---|
| **Attack Shark K86 (Rev 1)** | `3151:4015` | `1168` | `yc3121` (família yc500) | **Suportado & Verificado** |
| **Attack Shark K86 (Rev 2)** | `3151:5002` | `2730` | `yc3123` (família gen2) | **Suportado & Verificado** |
| **Attack Shark K86 (Rev 3)** | `3151:5056` | `4094` | `ry6602` (família gen2) | *Não suportado* (chip de tela separado) |

> **Nota sobre a Revisão 1 (`1168`):** A transmissão de dados, handshake de prontidão e gravação na flash foram verificados em hardware. O limite exato de quadros suportado pela flash da Revisão 1 permanece sem documentação oficial; o padrão seguro adotado é de 60 quadros.

---

## 📋 Requisitos

* **Sistema Operacional:** Linux (Kernel 5.4+ com módulo `hidraw` ativo).
* **Conexão:** **Obrigatório cabo USB**. Receptores sem fio 2.4 GHz e Bluetooth não expõem os endpoints de transferência de tela.
* **Dependências Python:** Python 3.10+ e Pillow:
  ```bash
  sudo apt install python3-pil
  # ou: pip install pillow
  ```
* **Dependências da Janela Nativa (Padrão):**
  * Debian / Ubuntu / Zorin OS: `sudo apt install python3-gi gir1.2-webkit2-4.1` (geralmente já instalado).
  * Arch Linux: `sudo pacman -S python-gobject webkit2gtk-4.1`
  * Fedora: `sudo dnf install python3-gobject webkit2gtk4.1`
  *(Caso o WebKit2GTK não esteja presente, o app iniciará um fallback seguro de navegador protegido por token aleatório).*

---

## 🚀 Instalação e Uso

### 1. Instalação Automática (Atalho + Permissões)

Execute o instalador:

```bash
./install.sh
```

O script irá:
1. Gerar e instalar o atalho `.desktop` em `~/.local/share/applications/` com caminhos dinâmicos.
2. Copiar o ícone para o tema do usuário.
3. Configurar a regra do `udev` para permitir gravação sem `sudo`.

*Após a instalação, desconecte e reconecte o cabo USB do teclado.*

### 2. Abrindo a Interface Visual

* Pelo menu de aplicativos do sistema: busque por **"Attack Shark K86 Screen"**.
* Ou pelo terminal:
  ```bash
  ./k86_gif_uploader.py
  ```

### 3. Linha de Comando (CLI)

```bash
# Enviar com configurações padrão:
./k86_gif_uploader.py minha_animacao.gif

# Ajustar velocidade da animação (menor = mais rápido; faixa comum 20 a 60):
./k86_gif_uploader.py minha_animacao.gif --delay 35

# Limitar a 45 quadros:
./k86_gif_uploader.py minha_animacao.gif --max-frames 45

# Salvar pré-visualização local antes de enviar:
./k86_gif_uploader.py minha_animacao.gif --preview

# Simulação sem gravar na flash (dry-run):
./k86_gif_uploader.py minha_animacao.gif --dry-run
```

---

## 🎨 Onde Encontrar GIFs para o K86

A tela possui resolução nativa de **240×135 pixels** (proporção 16:9). Animações horizontais e pixel art em loop produzem os melhores resultados:

* **[Pinterest - GIFs para Attack Shark K86](https://br.pinterest.com/mayssarf/gifs-for-attack-shark-k86):** Pasta com diversas animações compatíveis organizadas pela comunidade.
* **[Pinterest - GIFs para Telas de Teclado](https://www.pinterest.com/ideas/keyboard-oled-gifs/960337052007/):** Coleção geral de animações para displays OLED e TFT.
* **[k86-screen-frames (Marcel Pietron)](https://github.com/marcel-pietron/k86-screen-frames):** Contém o terminal verde retrô Unix (`shell_240x135.gif`) feito sob medida para 240×135.
* **[GIPHY](https://giphy.com/) & [Tenor](https://tenor.com/):** Busque por termos como `pixel art loop`, `bongo cat loop`, `lofi pixel art` ou `cyberpunk pixel art`.

---

## 🔧 Solução de Problemas

* **Permissão negada em `/dev/hidrawX`:**
  Instale a regra udev e reconecte o cabo USB:
  ```bash
  echo 'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="3151", ATTRS{idProduct}=="4015|5002", MODE="0660", TAG+="uaccess"' | sudo tee /etc/udev/rules.d/70-attack-shark-k86.rules
  sudo udevadm control --reload-rules && sudo udevadm trigger
  ```
* **"A tela não respondeu com o sinal de confirmação (ready)":**
  Conecte o teclado diretamente ao computador (evite hubs USB sem alimentação). Feche ferramentas que possam estar ocupando a interface HID (como o `sharkfin`).
* **Faixa branca ou imagem estagnada:**
  Envie uma única imagem estática (`.png`) para limpar o buffer de memória da tela.

---

## 📜 Créditos e Projetos Anteriores

Este software utiliza a documentação de engenharia reversa do protocolo USB HID mantida pela comunidade:

* **[sharkfin](https://github.com/dniminenn/sharkfin)** por JR Lanteigne (GPL-3.0-or-later) – Mapeamento do protocolo HID ROYUAN e registro de dispositivos.
* **[k86-screen-frames](https://github.com/marcel-pietron/k86-screen-frames)** por Marcel Pietron (GPL-3.0-or-later) – Pesquisa de handshake de múltiplos quadros no hardware K86 revisão 2730.

## ⚖️ Isenção de Responsabilidade e Licença

Este é um projeto independente de código aberto e **não é afiliado, patrocinado ou endossado pela Attack Shark, Shenzhen ROYUAN Technology ou suas associadas**. Todos os nomes de produtos e marcas registradas pertencem aos seus respectivos proprietários.

Distribuído sob a licença **GNU General Public License v3.0 ou posterior (GPL-3.0-or-later)**. Consulte o arquivo [LICENSE](LICENSE) para mais detalhes.
