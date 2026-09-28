#!/usr/bin/env python3
"""Atualiza os selos de tecnologias nos READMEs a partir das linguagens dos
repositorios do dono da conta.

Roda no GitHub Actions. Exige o secret TECH_TOKEN (Personal Access Token com
escopo para ler os repositorios). Le apenas o trecho entre <!-- TECH:START -->
e <!-- TECH:END --> e o reescreve; o resto do README nao e tocado.

Cada tecnologia recebe uma cor pseudoaleatoria derivada do proprio nome: fica
sempre a mesma enquanto fizer parte da lista, e nenhuma cor se repete entre as
tecnologias exibidas. Nenhum selo exibe icone/logo.
"""

import colorsys
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
MARCADOR = re.compile(r"<!-- TECH:START -->.*?<!-- TECH:END -->", re.S)

TOKEN = os.environ.get("TECH_TOKEN", "")
MAX = int(os.environ.get("MAX_LINGUAGENS") or "8")
IGNORAR = {
    nome.strip().lower()
    for nome in os.environ.get("IGNORAR_REPOS", "").split(",")
    if nome.strip()
}

# Distancia minima (em graus) entre as matizes exibidas, para nao sairem
# parecidas. Com no maximo 8 selos, sobra espaco de sobra no circulo.
SEPARACAO_MINIMA = 22.0
ANGULO_AUREO = 137.5


def api(caminho):
    requisicao = urllib.request.Request(
        API + caminho,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "atualizar-tecnologias",
        },
    )
    with urllib.request.urlopen(requisicao) as resposta:
        return json.load(resposta)


def listar_repos():
    repos, pagina = [], 1
    while True:
        lote = api(f"/user/repos?per_page=100&affiliation=owner&page={pagina}")
        repos.extend(lote)
        if len(lote) < 100:
            return repos
        pagina += 1


def somar_linguagens(repos):
    total = {}
    for repo in repos:
        try:
            dados = api(f"/repos/{repo['full_name']}/languages")
        except urllib.error.HTTPError as erro:
            print(f"aviso: ignorando {repo['full_name']} ({erro.code})", file=sys.stderr)
            continue
        for nome, tamanho in dados.items():
            total[nome] = total.get(nome, 0) + tamanho
    return total


def hsl_para_hex(matiz, saturacao, luz):
    vermelho, verde, azul = colorsys.hls_to_rgb(matiz / 360, luz, saturacao)
    return f"{round(vermelho * 255):02X}{round(verde * 255):02X}{round(azul * 255):02X}"


def distancia_matiz(a, b):
    bruta = abs(a - b) % 360
    return min(bruta, 360 - bruta)


def cor_da_tecnologia(nome, matizes_usadas):
    """Cor estavel por nome: deriva matiz/saturacao/luz de um hash do nome e
    afasta a matiz das ja usadas (de forma deterministica) ate nao repetir."""
    valor = int.from_bytes(
        hashlib.sha256(f"tecnologias:{nome}".encode("utf-8")).digest()[:8], "big"
    )
    matiz = (valor % 360000) / 1000.0
    saturacao = 0.45 + ((valor >> 20) % 31) / 100.0
    luz = 0.28 + ((valor >> 30) % 15) / 100.0
    for _ in range(40):
        if all(
            distancia_matiz(matiz, usada) >= SEPARACAO_MINIMA
            for usada in matizes_usadas
        ):
            break
        matiz = (matiz + ANGULO_AUREO) % 360
    matizes_usadas.append(matiz)
    return hsl_para_hex(matiz, saturacao, luz)


def rotulo_shields(nome):
    return (
        nome.replace("_", "__")
        .replace("-", "--")
        .replace(" ", "_")
        .replace("+", "%2B")
        .replace("#", "%23")
    )


def montar_badge(nome, cor):
    url = f"https://img.shields.io/badge/{rotulo_shields(nome)}-{cor}?style=for-the-badge"
    return f"![{nome}]({url})"


def montar_bloco(total):
    ranking = sorted(total.items(), key=lambda item: item[1], reverse=True)[:MAX]
    nomes = [nome for nome, _ in ranking]
    # A cor e atribuida na ordem alfabetica, e nao na ordem de uso, para que
    # mudar o ranking (bytes) nao troque a cor de quem ja estava na lista.
    matizes_usadas = []
    cores = {nome: cor_da_tecnologia(nome, matizes_usadas) for nome in sorted(nomes)}
    linhas = ["<!-- TECH:START -->"]
    linhas += [montar_badge(nome, cores[nome]) for nome in nomes]
    linhas += ["<!-- TECH:END -->"]
    return "\n".join(linhas)


def atualizar_arquivo(caminho, bloco):
    with open(caminho, encoding="utf-8") as arquivo:
        texto = arquivo.read()
    if not MARCADOR.search(texto):
        print(f"aviso: {caminho} nao tem os marcadores TECH.", file=sys.stderr)
        return False
    novo = MARCADOR.sub(lambda _: bloco, texto)
    if novo == texto:
        return False
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(novo)
    return True


def main():
    if not TOKEN:
        sys.exit(
            "Erro: defina o secret TECH_TOKEN "
            "(Personal Access Token com escopo para ler seus repositorios)."
        )
    repos = [
        repo
        for repo in listar_repos()
        if not repo["fork"] and repo["name"].lower() not in IGNORAR
    ]
    total = somar_linguagens(repos)
    if not total:
        print("Nenhuma linguagem encontrada; nada a atualizar.", file=sys.stderr)
        return
    bloco = montar_bloco(total)
    mudou = False
    for caminho in ("README.md", "README.pt-BR.md"):
        if os.path.exists(caminho):
            mudou = atualizar_arquivo(caminho, bloco) or mudou
    ranking = ", ".join(
        f"{nome} ({tamanho})"
        for nome, tamanho in sorted(total.items(), key=lambda i: i[1], reverse=True)[:MAX]
    )
    print(f"Linguagens (bytes): {ranking}")
    print("READMEs atualizados." if mudou else "Sem mudancas.")


if __name__ == "__main__":
    main()
