from .carteira import Carteira

import os
import subprocess
import sys
import chromedriver_autoinstaller

def install_system_dependencies():
    """
    Tenta instalar o Google Chrome em ambiente Linux (Debian/Ubuntu/Colab).
    Requer permissões de root/sudo.
    """
    print("Verificando e instalando dependências do sistema (Google Chrome)...")
    
    # Comandos que você usava no Colab
    commands = [
        "wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb",
        "apt-get update", # É bom dar um update antes
        "apt-get install -y ./google-chrome-stable_current_amd64.deb"
    ]

    try:
        for cmd in commands:
            # Executa o comando no shell
            subprocess.run(cmd, shell=True, check=True)
        print("Google Chrome instalado com sucesso!")
        
        # Instala/Atualiza o driver
        print("Configurando ChromeDriver...")
        chromedriver_autoinstaller.install()
        print("Ambiente pronto para uso.")
        
    except subprocess.CalledProcessError as e:
        print(f"Erro ao instalar dependências: {e}")
        print("Nota: Esta função foi feita para rodar em Linux (Colab/Ubuntu) com permissão sudo.")