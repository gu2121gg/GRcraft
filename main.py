import sys
import os
import uuid
import minecraft_launcher_lib
import subprocess
import configparser # Importa o módulo para salvar/carregar configurações
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QMessageBox, QFrame, QSlider, QFileDialog,
    QStackedWidget, QProgressBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QPixmap, QPalette, QBrush, QColor, QPainter, QPen, QImage
from datetime import datetime
import random

# Thread para instalação de bibliotecas para não travar a UI
class LibraryInstallerThread(QThread):
    installation_finished = pyqtSignal(bool, str) # Sinal (sucesso, mensagem de erro)
    status_message = pyqtSignal(str) # Sinal para enviar mensagens de status para a UI

    def __init__(self, version, game_directory):
        super().__init__()
        self.version = version
        self.game_directory = game_directory

    def run(self):
        try:
            self.status_message.emit("Verificando e instalando bibliotecas necessárias...")
            minecraft_launcher_lib.install.install_minecraft_version(self.version, self.game_directory)
            self.status_message.emit("Bibliotecas instaladas com sucesso!")
            self.installation_finished.emit(True, "")
        except Exception as e:
            self.status_message.emit(f"Erro: Falha ao instalar bibliotecas: {str(e)}")
            self.installation_finished.emit(False, str(e))

# Thread para o lançamento do jogo para não travar a UI
class GameLauncherThread(QThread):
    launch_finished = pyqtSignal(bool, str, str) # Sinal (sucesso, mensagem, nickname)
    status_message = pyqtSignal(str) # Sinal para enviar mensagens de status para a UI

    def __init__(self, version, game_directory, nickname, ram_allocation):
        super().__init__()
        self.version = version
        self.game_directory = game_directory
        self.nickname = nickname
        self.ram_allocation = ram_allocation

    def run(self):
        try:
            # Validação de nickname já feita na UI, mas pode ser reforçada aqui se necessário
            if not self.nickname or len(self.nickname) < 3 or len(self.nickname) > 16:
                self.status_message.emit("Erro: Nickname deve ter entre 3 e 16 caracteres.")
                self.launch_finished.emit(False, "Nickname inválido.", self.nickname)
                return

            self.status_message.emit(f"Tentando iniciar Minecraft com o nickname: {self.nickname}")
            self.status_message.emit(f"Alocação de RAM: {self.ram_allocation}GB")

            # Verificar se a versão existe
            self.status_message.emit("Verificando se a versão existe...")
            if not minecraft_launcher_lib.utils.is_version_valid(self.version, self.game_directory):
                self.status_message.emit(f"Erro: Versão {self.version} não encontrada em {self.game_directory}")
                self.launch_finished.emit(False, f"Versão {self.version} não encontrada.", self.nickname)
                return
            self.status_message.emit("Versão encontrada.")

            # Verificar instalação do Java
            self.status_message.emit("Verificando instalação do Java...")
            try:
                subprocess.check_output(["java", "-version"], stderr=subprocess.STDOUT, shell=True)
                self.status_message.emit("Java encontrado.")
            except subprocess.CalledProcessError:
                self.status_message.emit("Erro: Java não encontrado ou não instalado corretamente.")
                self.launch_finished.emit(False, "Java não está instalado ou não está no PATH. Por favor, instale o Java 8.", self.nickname)
                return

            # Verificar arquivo authlib
            authlib_path = os.path.join(self.game_directory, "libraries", "com", "mojang", "authlib", "1.5.21", "authlib-1.5.21.jar")
            self.status_message.emit(f"Verificando authlib em: {authlib_path}")
            if not os.path.exists(authlib_path):
                self.status_message.emit(f"Erro: authlib-1.5.21.jar não encontrado em {authlib_path}")
                self.launch_finished.emit(False, f"authlib-1.5.21.jar não encontrado. Garanta que as bibliotecas estão instaladas corretamente.", self.nickname)
                return
            self.status_message.emit("authlib-1.5.21.jar encontrado.")

            # Gerar UUID para modo offline
            self.status_message.emit("Gerando UUID para o modo offline...")
            offline_uuid = str(uuid.uuid4())
            self.status_message.emit(f"UUID Gerado: {offline_uuid}")

            # Definir opções de lançamento offline
            self.status_message.emit("Preparando opções de lançamento...")
            jvm_arguments = [f"-Xmx{self.ram_allocation}G", f"-Xms{int(self.ram_allocation/2)}G"] # Define Xms como metade de Xmx
            options = {
                "username": self.nickname,
                "uuid": offline_uuid,
                "token": "0",  # Token dummy para modo offline
                "gameDirectory": self.game_directory,
                "version": self.version,
                "jvmArguments": jvm_arguments
            }

            # Obter comando de lançamento
            self.status_message.emit("Gerando comando de lançamento...")
            minecraft_command = minecraft_launcher_lib.command.get_minecraft_command(
                self.version, self.game_directory, options
            )
            self.status_message.emit(f"Comando de lançamento: {' '.join(minecraft_command)}")

            # Iniciar o jogo
            self.status_message.emit("Iniciando Minecraft...")
            process = subprocess.run(minecraft_command, shell=True, capture_output=True, text=True)

            if process.returncode == 0:
                self.status_message.emit("Minecraft iniciado com sucesso!")
                self.launch_finished.emit(True, f"Minecraft iniciado no modo offline como {self.nickname}!", self.nickname)
            else:
                self.status_message.emit(f"Erro: Processo do Minecraft falhou com código de saída {process.returncode}")
                self.status_message.emit(f"Saída do processo: {process.stderr}")
                self.launch_finished.emit(False, f"Falha ao iniciar Minecraft. Verifique os logs para detalhes.", self.nickname)

        except Exception as e:
            self.status_message.emit(f"Erro: Falha ao iniciar Minecraft: {str(e)}")
            self.launch_finished.emit(False, f"Falha ao iniciar Minecraft: {str(e)}", self.nickname)

# Widget para a animação de partículas
class ParticleWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.particles = []
        self.num_particles = 50
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_particles)
        self.timer.start(30) # Atualiza a cada 30 ms

    def add_particle(self):
        size = random.randint(2, 5)
        x = random.randint(0, self.width())
        y = random.randint(0, self.height())
        speed_x = random.uniform(-0.5, 0.5)
        speed_y = random.uniform(-0.5, 0.5)
        alpha = random.randint(100, 200) # Transparência inicial
        color = QColor(random.randint(100, 200), random.randint(100, 200), random.randint(200, 255), alpha) # Tons de azul/verde
        self.particles.append({'x': x, 'y': y, 'size': size, 'speed_x': speed_x, 'speed_y': speed_y, 'color': color, 'alpha': alpha}) # Adiciona 'alpha' ao dicionário

    def update_particles(self):
        for p in self.particles:
            p['x'] += p['speed_x']
            p['y'] += p['speed_y']
            p['alpha'] -= 1 # Fading out

            # Reinicia a partícula se sair da tela ou desaparecer
            if not (0 <= p['x'] <= self.width() and 0 <= p['y'] <= self.height()) or p['alpha'] <= 0:
                # Reinicia as propriedades da partícula em vez de removê-la
                p['x'] = random.randint(0, self.width())
                p['y'] = random.randint(0, self.height())
                p['speed_x'] = random.uniform(-0.5, 0.5)
                p['speed_y'] = random.uniform(-0.5, 0.5)
                p['alpha'] = random.randint(100, 200)
                p['size'] = random.randint(2, 5)
                p['color'] = QColor(random.randint(100, 200), random.randint(100, 200), random.randint(200, 255), p['alpha'])


        # Garante que sempre haja o número desejado de partículas
        while len(self.particles) < self.num_particles:
            self.add_particle()

        self.update() # Redesenha o widget

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        for p in self.particles:
            color = p['color']
            # Garante que o valor de alpha seja válido (entre 0 e 255)
            current_alpha = max(0, min(255, p['alpha']))
            color.setAlpha(current_alpha)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(int(p['x']), int(p['y']), p['size'], p['size'])


class MinecraftOfflineLauncher(QMainWindow):
    CONFIG_FILE = "launcher_settings.ini" # Nome do arquivo de configuração

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Minecraft Offline Launcher (Forge 1.8.8) com Logs")
        self.setFixedSize(1280, 720) # Define o tamanho fixo da janela

        # Definir diretório do jogo e versão
        self.game_directory = r"C:\Users\Gu\Desktop\GRcraft" # Altere para o seu diretório
        self.version = "1.8.8-forge1.8.8-11.15.0.1655" # Altere para a sua versão
        self.ram_allocation = 2 # RAM padrão em GB (será sobrescrito se houver configurações salvas)

        # Inicializar QStackedWidget
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # Adicionar animação de partículas ao fundo da janela principal
        self.particle_widget = ParticleWidget(self)
        self.particle_widget.setGeometry(self.rect())
        self.particle_widget.lower() # Envia para o fundo

        # Criar as páginas do menu e do launcher
        self.create_menu_page()
        self.create_launcher_page() # Este método agora cria a página principal do launcher E a barra lateral de configurações

        # Aplicar tema escuro e imagem de fundo (aplicado à QMainWindow)
        self.apply_dark_theme()

        # Carregar configurações salvas
        self.load_settings()

        # Iniciar a instalação das bibliotecas apenas quando o launcher for exibido
        self.installer_thread = LibraryInstallerThread(self.version, self.game_directory)
        self.installer_thread.installation_finished.connect(self.on_libraries_installed)
        self.installer_thread.status_message.connect(self.update_status_bar) # Conecta ao novo slot
        
        # Thread do GameLauncher
        self.launcher_thread = GameLauncherThread(self.version, self.game_directory, "", self.ram_allocation)
        self.launcher_thread.launch_finished.connect(self.on_game_launched)
        self.launcher_thread.status_message.connect(self.update_status_bar) # Conecta ao novo slot

    def closeEvent(self, event):
        """Sobrescreve o evento de fechamento da janela para salvar as configurações."""
        self.save_settings()
        event.accept()

    def load_settings(self):
        """Carrega as configurações salvas do arquivo INI."""
        config = configparser.ConfigParser()
        if os.path.exists(self.CONFIG_FILE):
            config.read(self.CONFIG_FILE)
            if 'LauncherSettings' in config:
                settings = config['LauncherSettings']
                last_nickname = settings.get('last_nickname', '')
                last_ram = settings.getint('last_ram_gb', self.ram_allocation)

                self.nickname_input.setText(last_nickname)
                self.ram_allocation = last_ram
                self.ram_slider.setValue(last_ram)
                self.update_status_bar("Configurações carregadas.")
            else:
                self.update_status_bar("Arquivo de configurações encontrado, mas sem seção 'LauncherSettings'. Usando padrões.")
        else:
            self.update_status_bar("Arquivo de configurações não encontrado. Usando configurações padrão.")

    def save_settings(self):
        """Salva as configurações atuais no arquivo INI."""
        config = configparser.ConfigParser()
        config['LauncherSettings'] = {
            'last_nickname': self.nickname_input.text(),
            'last_ram_gb': str(self.ram_allocation)
        }
        try:
            with open(self.CONFIG_FILE, 'w') as configfile:
                config.write(configfile)
            self.update_status_bar("Configurações salvas!")
        except Exception as e:
            self.update_status_bar(f"Erro ao salvar configurações: {str(e)}")


    def create_menu_page(self):
        menu_widget = QWidget()
        menu_layout = QVBoxLayout(menu_widget)
        menu_layout.setAlignment(Qt.AlignCenter)
        menu_layout.setSpacing(30)

        menu_title_label = QLabel("GRcraft") # Título alterado para "GRcraft"
        menu_title_label.setAlignment(Qt.AlignCenter)
        menu_title_label.setObjectName("menuTitleLabel")
        menu_layout.addWidget(menu_title_label)

        start_button = QPushButton("Iniciar GRcraft")
        start_button.setObjectName("startButton")
        start_button.clicked.connect(self.show_launcher_page)
        menu_layout.addWidget(start_button)

        self.stacked_widget.addWidget(menu_widget) # Adiciona a página do menu

    def create_launcher_page(self):
        launcher_widget = QWidget()
        # Usa QHBoxLayout para a área de conteúdo principal para acomodar a barra lateral
        main_h_layout = QHBoxLayout(launcher_widget)
        main_h_layout.setContentsMargins(20, 20, 20, 20)
        main_h_layout.setSpacing(15)

        # --- Área de Conteúdo Principal (Lado Esquerdo) ---
        main_content_v_layout = QVBoxLayout()
        main_content_v_layout.setSpacing(15)

        # Top Bar (Configurações e Abrir Mods)
        top_bar_layout = QHBoxLayout()
        top_bar_layout.addStretch() # Empurra os botões para a direita

        self.mods_button = QPushButton("Abrir Pasta de Mods") # Botão de mods movido para a barra superior
        self.mods_button.setObjectName("modsButton")
        self.mods_button.clicked.connect(self.open_mods_folder)
        top_bar_layout.addWidget(self.mods_button)

        self.settings_button = QPushButton("⚙️") # Ícone de engrenagem Unicode
        self.settings_button.setObjectName("settingsButton")
        self.settings_button.setFixedSize(40, 40) # Tamanho fixo para o botão de ícone
        self.settings_button.clicked.connect(self.toggle_settings_sidebar)
        top_bar_layout.addWidget(self.settings_button)
        main_content_v_layout.addLayout(top_bar_layout)

        # Título
        title_label = QLabel("Minecraft Offline Launcher")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setObjectName("titleLabel")
        main_content_v_layout.addWidget(title_label)

        # Frame de Controle (Nickname, Lançamento)
        control_frame = QFrame()
        control_frame.setObjectName("controlFrame")
        control_layout = QVBoxLayout(control_frame)
        control_layout.setSpacing(10)

        # Entrada de Nickname
        nickname_layout = QHBoxLayout()
        nickname_label = QLabel("Nickname:")
        nickname_label.setObjectName("inputLabel")
        nickname_layout.addWidget(nickname_label)
        self.nickname_input = QLineEdit()
        self.nickname_input.setPlaceholderText("Digite seu nickname (3-16 caracteres)")
        self.nickname_input.setObjectName("nicknameInput")
        self.nickname_input.textChanged.connect(self.validate_nickname)
        nickname_layout.addWidget(self.nickname_input)
        control_layout.addLayout(nickname_layout)

        # Botão de Lançamento
        self.launch_button = QPushButton("Iniciar Minecraft (Offline)")
        self.launch_button.setObjectName("launchButton")
        self.launch_button.clicked.connect(self.start_game_launch)
        control_layout.addWidget(self.launch_button)

        main_content_v_layout.addWidget(control_frame)

        # Barra de Progresso (substitui os logs)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setTextVisible(True) # Mostra o texto de status
        self.progress_bar.setFormat("Aguardando...") # Texto inicial
        self.progress_bar.setRange(0, 100) # Modo determinado inicialmente
        self.progress_bar.setValue(0)
        main_content_v_layout.addWidget(self.progress_bar)

        main_content_v_layout.addStretch()

        # Adiciona o conteúdo principal ao QHBoxLayout
        main_h_layout.addLayout(main_content_v_layout)

        # --- Barra Lateral de Configurações (Lado Direito) ---
        self.settings_sidebar = QFrame()
        self.settings_sidebar.setObjectName("settingsSidebar")
        self.settings_sidebar.setFixedWidth(0) # Inicialmente oculto/colapsado
        self.settings_sidebar.setVisible(False) # Garante que não esteja visível inicialmente

        self.settings_sidebar_layout = QVBoxLayout(self.settings_sidebar)
        self.settings_sidebar_layout.setContentsMargins(15, 15, 15, 15) # Margens internas para a sidebar
        self.settings_sidebar_layout.setSpacing(10)
        self.settings_sidebar_layout.setAlignment(Qt.AlignTop)

        # Botão de Fechar para a barra lateral
        close_settings_button = QPushButton("X")
        close_settings_button.setObjectName("closeSettingsButton")
        close_settings_button.setFixedSize(30, 30)
        close_settings_button.clicked.connect(self.toggle_settings_sidebar)
        close_button_layout = QHBoxLayout()
        close_button_layout.addStretch()
        close_button_layout.addWidget(close_settings_button)
        self.settings_sidebar_layout.addLayout(close_button_layout)

        settings_title_label = QLabel("Configurações")
        settings_title_label.setAlignment(Qt.AlignCenter)
        settings_title_label.setObjectName("settingsTitleLabel")
        self.settings_sidebar_layout.addWidget(settings_title_label)

        # Configuração de RAM (movida para cá)
        ram_label = QLabel("Alocação de RAM:")
        ram_label.setObjectName("inputLabel")
        self.settings_sidebar_layout.addWidget(ram_label)

        self.ram_slider = QSlider(Qt.Horizontal)
        self.ram_slider.setMinimum(1)
        self.ram_slider.setMaximum(14)
        self.ram_slider.setValue(self.ram_allocation)
        self.ram_slider.setTickPosition(QSlider.TicksBelow)
        self.ram_slider.setTickInterval(1)
        self.ram_slider.valueChanged.connect(self.update_ram_label)
        self.settings_sidebar_layout.addWidget(self.ram_slider)

        self.ram_value_label = QLabel(f"{self.ram_allocation} GB")
        self.ram_value_label.setObjectName("ramValueLabel")
        self.settings_sidebar_layout.addWidget(self.ram_value_label)

        self.settings_sidebar_layout.addStretch() # Empurra o conteúdo para o topo

        # Adiciona a barra lateral de configurações ao QHBoxLayout principal
        main_h_layout.addWidget(self.settings_sidebar)

        # Adiciona a página do launcher ao QStackedWidget
        self.stacked_widget.addWidget(launcher_widget)

    def show_launcher_page(self):
        self.stacked_widget.setCurrentIndex(1) # Muda para a página do launcher
        # Inicia a instalação das bibliotecas apenas quando o launcher é exibido
        self.installer_thread.start()

    def toggle_settings_sidebar(self):
        # Define a largura desejada da barra lateral quando expandida
        sidebar_width = 300

        # Animação para expandir/colapsar a barra lateral
        self.animation = QPropertyAnimation(self.settings_sidebar, b"minimumWidth")
        self.animation.setDuration(300) # Duração da animação em ms
        self.animation.setEasingCurve(QEasingCurve.InOutQuad) # Curva de aceleração/desaceleração

        if self.settings_sidebar.width() > 0: # Se a barra lateral estiver visível (largura > 0)
            self.animation.setStartValue(sidebar_width)
            self.animation.setEndValue(0)
            self.animation.finished.connect(lambda: self.settings_sidebar.setVisible(False)) # Esconde após colapsar
        else:
            self.settings_sidebar.setVisible(True) # Mostra antes de expandir
            self.animation.setStartValue(0)
            self.animation.setEndValue(sidebar_width)

        self.animation.start()


    def apply_dark_theme(self):
        # Carregar imagem de fundo
        try:
            # Substitua 'Image_fx.jpg' pelo caminho real da sua imagem
            # Certifique-se de que a imagem está no mesmo diretório do script ou forneça o caminho completo
            background_image_path = "Image_fx.jpg" # Caminho para a imagem de fundo
            pixmap = QPixmap(background_image_path)
            if pixmap.isNull():
                self.update_status_bar(f"Aviso: Não foi possível carregar a imagem de fundo: {background_image_path}. Usando cor sólida.")
                background_style = "background-color: #2e2e2e;"
            else:
                # Redimensionar a imagem para caber na janela
                scaled_pixmap = pixmap.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                palette = self.palette()
                palette.setBrush(QPalette.Window, QBrush(scaled_pixmap))
                self.setPalette(palette)
                background_style = "" # A imagem de fundo é definida pela paleta
        except Exception as e:
            self.update_status_bar(f"Erro ao carregar imagem de fundo: {str(e)}. Usando cor sólida.")
            background_style = "background-color: #2e2e2e;"


        # Estilos CSS para um tema escuro e moderno
        self.setStyleSheet(f"""
            QMainWindow {{
                {background_style} /* Fundo principal (imagem ou cor) */
                color: #e0e0e0; /* Cor do texto padrão */
                font-family: 'Segoe UI', sans-serif;
            }}

            #menuTitleLabel {{
                font-size: 36px;
                font-weight: bold;
                color: #4CAF50;
                margin-bottom: 40px;
                background-color: rgba(0, 0, 0, 0.6);
                padding: 20px;
                border-radius: 15px;
            }}

            #startButton {{
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 15px 40px;
                font-size: 24px;
                font-weight: bold;
                transition: background-color 0.3s ease;
            }}
            #startButton:hover {{
                background-color: #45a049;
            }}
            #startButton:pressed {{
                background-color: #3e8e41;
            }}

            #settingsButton {{
                background-color: transparent;
                border: none;
                font-size: 24px; /* Tamanho do ícone de engrenagem */
                color: #e0e0e0;
                padding: 5px;
                qproperty-iconSize: 32px; /* Ajusta o tamanho se for um QIcon */
            }}
            #settingsButton:hover {{
                color: #4CAF50; /* Muda a cor ao passar o mouse */
            }}
            #settingsButton:pressed {{
                color: #3e8e41;
            }}

            #settingsSidebar {{
                background-color: rgba(45, 45, 45, 0.9); /* Fundo da sidebar, um pouco mais opaco */
                border-left: 2px solid #4CAF50; /* Borda verde à esquerda */
                border-radius: 10px;
                padding: 15px;
            }}

            #closeSettingsButton {{
                background-color: #FF5733; /* Vermelho para o botão de fechar */
                color: white;
                border: none;
                border-radius: 15px; /* Torna o botão circular */
                font-weight: bold;
            }}
            #closeSettingsButton:hover {{
                background-color: #e04a2c;
            }}

            #settingsTitleLabel {{
                font-size: 22px;
                font-weight: bold;
                color: #4CAF50;
                margin-bottom: 15px;
            }}

            #titleLabel {{
                font-size: 28px;
                font-weight: bold;
                color: #4CAF50; /* Verde vibrante para o título */
                margin-bottom: 20px;
                background-color: rgba(0, 0, 0, 0.5); /* Fundo semi-transparente para o título */
                padding: 10px;
                border-radius: 5px;
            }}

            #controlFrame {{
                background-color: rgba(60, 60, 60, 0.8); /* Fundo do frame de controle semi-transparente */
                border-radius: 10px;
                padding: 20px;
                border: 1px solid #555555;
            }}

            #inputLabel {{
                color: #e0e0e0;
                font-size: 16px;
                font-weight: 500;
            }}

            #nicknameInput {{
                background-color: #4a4a4a;
                border: 1px solid #666666;
                border-radius: 5px;
                padding: 8px;
                color: #ffffff;
                font-size: 15px;
            }}
            #nicknameInput:focus {{
                border: 1px solid #4CAF50; /* Borda verde ao focar */
            }}

            #ramValueLabel {{
                color: #e0e0e0;
                font-size: 15px;
                font-weight: bold;
                min-width: 60px; /* Garante espaço para o texto */
                text-align: center; /* Centraliza o texto do valor da RAM */
            }}

            QSlider::groove:horizontal {{
                border: 1px solid #555555;
                height: 8px;
                background: #3c3c3c;
                margin: 2px 0;
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: #4CAF50;
                border: 1px solid #4CAF50;
                width: 18px;
                margin: -5px 0; /* Centraliza o handle verticalmente */
                border-radius: 9px;
                transition: background-color 0.3s ease; /* Adiciona transição para o handle */
            }}
            QSlider::handle:horizontal:hover {{
                background: #3e8e41; /* Verde mais escuro no hover */
            }}
            QSlider::sub-page:horizontal {{
                background: #4CAF50; /* Cor da parte preenchida do slider */
                border: 1px solid #4CAF50;
                border-radius: 4px;
            }}

            #launchButton, #modsButton {{
                background-color: #4CAF50; /* Verde para os botões */
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 25px;
                font-size: 18px;
                font-weight: bold;
                margin-top: 10px;
                transition: background-color 0.3s ease; /* Transição suave */
            }}
            #launchButton:hover, #modsButton:hover {{
                background-color: #45a049; /* Verde mais escuro ao passar o mouse */
            }}
            #launchButton:pressed, #modsButton:pressed {{
                background-color: #3e8e41; /* Verde ainda mais escuro ao clicar */
            }}
            #launchButton:disabled {{
                background-color: #6a6a6a; /* Cinza para botão desabilitado */
                color: #cccccc;
            }}

            #progressBar {{
                border: 1px solid #555555;
                border-radius: 5px;
                text-align: center;
                color: #e0e0e0;
                background-color: #3c3c3c;
                height: 25px;
            }}
            #progressBar::chunk {{
                background-color: #4CAF50;
                border-radius: 4px;
            }}

            QMessageBox {{
                background-color: #3c3c3c;
                color: #e0e0e0;
                font-size: 14px;
            }}
            QMessageBox QPushButton {{
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px 10px;
            }}
            QMessageBox QPushButton:hover {{
                background-color: #45a049;
            }}
        """)

    def update_status_bar(self, message):
        """Atualiza o texto da barra de progresso."""
        if hasattr(self, 'progress_bar') and self.progress_bar is not None:
            self.progress_bar.setFormat(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
            # Se a mensagem indica um processo ativo, coloque a barra em modo indeterminado
            if "Verificando" in message or "instalando" in message or "Iniciando" in message or "Gerando" in message:
                self.progress_bar.setRange(0, 0) # Modo indeterminado
            else:
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(100) # Completo
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")


    def on_libraries_installed(self, success, error_message):
        """Slot chamado quando a instalação das bibliotecas termina."""
        if success:
            self.update_status_bar("Instalação de bibliotecas concluída. Pronto para iniciar o jogo.")
            self.launch_button.setEnabled(True) # Habilitar botão após a instalação
        else:
            self.update_status_bar(f"Erro crítico na instalação das bibliotecas: {error_message}")
            QMessageBox.critical(self, "Erro", f"Falha crítica ao instalar bibliotecas: {error_message}")
            self.launch_button.setEnabled(False) # Manter desabilitado se houver erro

    def validate_nickname(self):
        """Valida o nickname em tempo real e atualiza o estilo do input."""
        nickname = self.nickname_input.text().strip()
        if 3 <= len(nickname) <= 16:
            self.nickname_input.setStyleSheet("border: 1px solid #4CAF50;") # Borda verde para válido
            # Habilitar o botão de lançamento apenas se o nickname for válido E as libs estiverem instaladas
            # Verifica se a thread de instalação já terminou ou não está rodando
            if not self.installer_thread.isRunning():
                 self.launch_button.setEnabled(True)
            else:
                self.launch_button.setEnabled(False)
        else:
            self.nickname_input.setStyleSheet("border: 1px solid #FF5733;") # Borda vermelha para inválido
            self.launch_button.setEnabled(False) # Desabilitar se o nickname for inválido

    def update_ram_label(self, value):
        """Atualiza o label de exibição da RAM alocada."""
        self.ram_allocation = value
        self.ram_value_label.setText(f"{value} GB")
        self.save_settings() # Salva as configurações imediatamente ao mudar a RAM

    def start_game_launch(self):
        """Inicia o processo de lançamento do jogo em uma thread separada."""
        nickname = self.nickname_input.text().strip()

        if not nickname or len(nickname) < 3 or len(nickname) > 16:
            self.update_status_bar("Erro: Nickname deve ter entre 3 e 16 caracteres.")
            QMessageBox.critical(self, "Erro", "Por favor, digite um nickname válido (3-16 caracteres).")
            return

        self.launch_button.setEnabled(False) # Desabilitar botão durante o lançamento
        self.launch_button.setText("Iniciando...") # Feedback visual
        
        # Cria uma nova instância da thread de lançamento do jogo com os parâmetros corretos
        self.launcher_thread = GameLauncherThread(self.version, self.game_directory, nickname, self.ram_allocation)
        self.launcher_thread.launch_finished.connect(self.on_game_launched)
        self.launcher_thread.status_message.connect(self.update_status_bar)
        self.launcher_thread.start()


    def on_game_launched(self, success, message, nickname):
        """Slot chamado quando o lançamento do jogo termina."""
        self.launch_button.setEnabled(True) # Reabilitar botão
        self.launch_button.setText("Iniciar Minecraft (Offline)") # Resetar texto do botão

        if success:
            self.update_status_bar(f"Minecraft iniciado com sucesso como {nickname}!")
            QMessageBox.information(self, "Sucesso", message)
        else:
            self.update_status_bar(f"Falha ao iniciar Minecraft: {message}")
            QMessageBox.critical(self, "Erro", message)

    def open_mods_folder(self):
        """Abre a pasta de mods do Minecraft."""
        mods_path = os.path.join(self.game_directory, "mods")
        if not os.path.exists(mods_path):
            os.makedirs(mods_path) # Cria a pasta se não existir
            self.update_status_bar(f"Pasta de mods criada em: {mods_path}")

        try:
            if sys.platform == "win32":
                os.startfile(mods_path)
            elif sys.platform == "darwin": # macOS
                subprocess.Popen(["open", mods_path])
            else: # Linux
                subprocess.Popen(["xdg-open", mods_path])
            self.update_status_bar(f"Pasta de mods aberta: {mods_path}")
        except Exception as e:
            self.update_status_bar(f"Erro ao abrir pasta de mods: {str(e)}")
            QMessageBox.critical(self, "Erro", f"Não foi possível abrir a pasta de mods: {str(e)}")


def main():
    app = QApplication(sys.argv)
    launcher = MinecraftOfflineLauncher()
    launcher.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
