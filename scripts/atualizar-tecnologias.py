#!/usr/bin/env python3
"""Atualiza os selos de tecnologias nos READMEs a partir das linguagens dos
repositorios do dono da conta.

Roda no GitHub Actions. Exige o secret TECH_TOKEN (Personal Access Token com
escopo para ler os repositorios). Le apenas o trecho entre <!-- TECH:START -->
e <!-- TECH:END --> e o reescreve; o resto do README nao e tocado.

Cada selo recebe uma cor aleatoria propria; nenhuma cor se repete entre as
tecnologias exibidas. Nenhum selo exibe icone/logo.
"""

import colorsys
import json
import os
import random
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


def gerar_cores(quantidade):
    """Cores aleatorias, uma por tecnologia, todas diferentes.

    As matizes ficam em faixas separadas (para nao sairem parecidas) e a
    luminosidade fica baixa o bastante para o texto branco do selo ser legivel.
    """
    if quantidade <= 0:
        return []
    passo = 360.0 / quantidade
    deslocamento = random.uniform(0, 360)
    cores, usadas = [], set()
    for indice in range(quantidade):
        inicio = deslocamento + indice * passo
        for _ in range(50):
            cor = hsl_para_hex(
                (inicio + random.uniform(0, passo * 0.5)) % 360,
                random.uniform(0.45, 0.75),
                random.uniform(0.28, 0.42),
            )
            if cor not in usadas:
                break
        usadas.add(cor)
        cores.append(cor)
    return cores


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
    cores = gerar_cores(len(ranking))
    linhas = ["<!-- TECH:START -->"]
    linhas += [montar_badge(nome, cor) for (nome, _), cor in zip(ranking, cores)]
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
