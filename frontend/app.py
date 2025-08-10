from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# Rota para a página de Login
@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Adicione sua lógica de autenticação aqui
        return redirect(url_for('dashboard'))
    return render_template('login.html')

# Rota para a página de Registro
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Adicione sua lógica de registro de usuário aqui
        return redirect(url_for('login'))
    return render_template('register.html')

# Rota para o Dashboard
@app.route('/dashboard')
def dashboard():
    # Lógica para buscar o saldo e atividades do dia
    saldo = 1000  # Exemplo
    atividades = ["Aposta 1", "Aposta 2"] # Exemplo
    return render_template('dashboard.html', saldo=saldo, atividades=atividades)

# Rota para a página de criação de aposta
@app.route('/create_bet', methods=['GET', 'POST'])
def create_bet():
    if request.method == 'POST':
        # Lógica para processar a nova aposta
        return redirect(url_for('dashboard'))
    return render_template('create_bet.html')

# Rota para o histórico de apostas
@app.route('/history')
def history():
    # Lógica para buscar o histórico de apostas
    historico = ["Aposta 3 - Ganhadora", "Aposta 4 - Perdida"] # Exemplo
    return render_template('history.html', historico=historico)

if __name__ == '__main__':
    app.run(debug=True)