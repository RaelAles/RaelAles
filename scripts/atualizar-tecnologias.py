#!/usr/bin/env python3
"""Atualiza os selos de tecnologias nos READMEs a partir das linguagens dos
repositorios do dono da conta.

Roda no GitHub Actions. Exige o secret TECH_TOKEN (Personal Access Token com
escopo para ler os repositorios). Le apenas o trecho entre <!-- TECH:START -->
e <!-- TECH:END --> e o reescreve; o resto do README nao e tocado.
"""

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

# nome da linguagem -> (cor sem '#', slug do logo em simple-icons)
LINGUAGENS = {
    "JavaScript": ("F7DF1E", "javascript"),
    "TypeScript": ("3178C6", "typescript"),
    "Python": ("3572A5", "python"),
    "HTML": ("E34F26", "html5"),
    "CSS": ("1572B6", "css3"),
    "SCSS": ("C6538C", "sass"),
    "Shell": ("89E051", "gnubash"),
    "Bash": ("89E051", "gnubash"),
    "PowerShell": ("012456", "powershell"),
    "Lua": ("000080", "lua"),
    "Go": ("00ADD8", "go"),
    "Rust": ("DEA584", "rust"),
    "Java": ("B07219", "openjdk"),
    "C": ("555555", "c"),
    "C++": ("F34B7D", "cplusplus"),
    "C#": ("178600", "csharp"),
    "PHP": ("4F5D95", "php"),
    "Ruby": ("701516", "ruby"),
    "Kotlin": ("A97BFF", "kotlin"),
    "Swift": ("F05138", "swift"),
    "Dart": ("00B4AB", "dart"),
    "R": ("198CE7", "r"),
    "Scala": ("C22D40", "scala"),
    "Elixir": ("6E4A7E", "elixir"),
    "Haskell": ("5E5086", "haskell"),
    "Perl": ("0298C3", "perl"),
    "Vue": ("41B883", "vuedotjs"),
    "Svelte": ("FF3E00", "svelte"),
    "Astro": ("FF5A03", "astro"),
    "Dockerfile": ("384D54", "docker"),
    "Makefile": ("427819", ""),
    "Zig": ("EC915C", "zig"),
    "Nix": ("7E7EFF", "nixos"),
    "Clojure": ("DB5855", "clojure"),
    "Erlang": ("B83998", "erlang"),
    "Julia": ("A270BA", "julia"),
    "OCaml": ("3BE133", "ocaml"),
    "GDScript": ("355570", "godotengine"),
    "Solidity": ("AA6746", "solidity"),
    "Vim Script": ("199F4B", "vim"),
    "TeX": ("3D6117", "latex"),
    "Jupyter Notebook": ("DA5B0B", "jupyter"),
    "Markdown": ("083FA1", "markdown"),
    "CMake": ("DA3434", "cmake"),
    "Groovy": ("4298B8", "apachegroovy"),
    "Assembly": ("6E4C13", ""),
    "Batchfile": ("C1F12E", ""),
    "Objective-C": ("438EFF", ""),
}

COR_PADRAO = ("555555", "")


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


def luminancia(hexadecimal):
    def canal(valor):
        valor = int(valor, 16) / 255
        return valor / 12.92 if valor <= 0.03928 else ((valor + 0.055) / 1.055) ** 2.4

    r, g, b = (canal(hexadecimal[i : i + 2]) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def rotulo_shields(nome):
    return (
        nome.replace("_", "__")
        .replace("-", "--")
        .replace(" ", "_")
        .replace("+", "%2B")
        .replace("#", "%23")
    )


def montar_badge(nome):
    cor, logo = LINGUAGENS.get(nome, COR_PADRAO)
    cor = cor.lstrip("#").upper()
    cor_logo = "black" if luminancia(cor) > 0.5 else "white"
    url = f"https://img.shields.io/badge/{rotulo_shields(nome)}-{cor}?style=for-the-badge"
    if logo:
        url += f"&logo={logo}&logoColor={cor_logo}"
    return f"![{nome}]({url})"


def montar_bloco(total):
    ranking = sorted(total.items(), key=lambda item: item[1], reverse=True)[:MAX]
    linhas = ["<!-- TECH:START -->"]
    linhas += [montar_badge(nome) for nome, _ in ranking]
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
