# Gerador de Relatório · Meta Ads

Interface web para gerar relatórios de tráfego pago a partir de exports do Meta Ads Manager.

---

## Estrutura dos arquivos

```
relatorio-app/
├── app.py                  ← Backend (Flask)
├── gerar_relatorio_html.py ← Lógica de geração do relatório
├── requirements.txt        ← Dependências Python
├── render.yaml             ← Configuração de deploy no Render
└── static/
    └── index.html          ← Frontend (página web)
```

---

## Como fazer o deploy (passo a passo)

### 1. Criar conta no GitHub
1. Acesse https://github.com e clique em **Sign up**
2. Crie sua conta gratuitamente

### 2. Criar repositório no GitHub
1. Após fazer login, clique no **+** no canto superior direito → **New repository**
2. Dê um nome (ex: `relatorio-meta-ads`)
3. Deixe como **Public**
4. Clique em **Create repository**

### 3. Subir os arquivos
1. Na página do repositório criado, clique em **uploading an existing file**
2. Arraste todos os arquivos desta pasta para a área de upload
   - `app.py`
   - `gerar_relatorio_html.py`
   - `requirements.txt`
   - `render.yaml`
   - A pasta `static/` com o `index.html` dentro
3. Clique em **Commit changes**

### 4. Criar conta no Render
1. Acesse https://render.com e clique em **Get Started for Free**
2. Faça login com sua conta do GitHub (mais fácil)

### 5. Criar o serviço no Render
1. No painel do Render, clique em **New +** → **Web Service**
2. Conecte ao repositório `relatorio-meta-ads` que você criou
3. O Render vai detectar o `render.yaml` automaticamente
4. Clique em **Create Web Service**
5. Aguarde o deploy (leva ~2 minutos na primeira vez)
6. Quando aparecer **Live**, clique no link gerado (ex: `https://relatorio-meta-ads.onrender.com`)

---

## Como usar

1. Acesse o link do seu app no Render
2. Faça upload do arquivo `dados.csv` (export do Meta Ads Manager)
3. Escreva a análise no campo de texto
4. Clique em **Gerar Relatório**
5. O relatório aparece na tela — clique em **Baixar HTML** para salvar

---

## Observações

- O plano gratuito do Render "hiberna" o servidor após 15 minutos sem uso.
  Na primeira requisição depois disso, pode demorar ~30 segundos para acordar.
- Para evitar hibernação, faça upgrade para o plano pago ($7/mês) no Render.
- O arquivo CSV deve ser um export padrão do Meta Ads Manager com as colunas usuais.
