from pathlib import Path
import subprocess

def make_deploys():
    p = Path('.')
    deployment_files = list(p.glob('odissei/flows/*ingestion*.py'))
    for file in deployment_files:
        filename = str(file)
        subprocess.Popen(f'python3 {filename}', stdout=subprocess.PIPE)


def main():
    if __name__ == '__main__':
        make_deploys()
