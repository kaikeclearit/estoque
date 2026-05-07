#!/usr/bin/env python
"""
Script de Migração - Excel para Banco de Dados
Importa produtos, clientes e entradas do estoque
"""

import pandas as pd
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from core.models import Product, Client, StockEntry, ProductStock, Employee

def limpar_texto(texto):
    """Remove espaços e caracteres especiais"""
    if pd.isna(texto) or texto == '-' or texto == '':
        return None
    return str(texto).strip()

def limpar_numero(valor):
    """Converte para número"""
    if pd.isna(valor) or valor == '-' or valor == '':
        return None
    try:
        return int(float(valor))
    except:
        return None

def importar_produtos(arquivo):
    """Importa produtos da aba CADASTRO"""
    print("\n" + "="*60)
    print("📦 IMPORTANDO PRODUTOS")
    print("="*60)
    
    df = pd.read_excel(arquivo, sheet_name='CADASTRO', skiprows=1)
    
    # A planilha tem 14 colunas, vamos renomear todas
    colunas = ['ITEM', 'PRODUTO', 'FABRICANTE', 'CATEGORIA', 'MODELO', 
               'MAO', 'SP', 'RJ', 'OUTROS', 'TOTAL', 'STATUS', 'OBS', 'OBS2', 'OBS3']
    
    # Ajustar para o número real de colunas
    if len(df.columns) != len(colunas):
        colunas = colunas[:len(df.columns)]
    
    df.columns = colunas
    
    produtos_criados = 0
    stocks_criados = 0
    
    for idx, row in df.iterrows():
        try:
            nome = limpar_texto(row.get('PRODUTO'))
            if not nome:
                continue
            
            # Criar produto
            produto, criado = Product.objects.update_or_create(
                name=nome,
                defaults={
                    'manufacturer': limpar_texto(row.get('FABRICANTE')) or '',
                    'model': limpar_texto(row.get('MODELO')) or '',
                    'product_id': limpar_texto(row.get('ITEM')),
                }
            )
            
            if criado:
                produtos_criados += 1
                print(f"✓ {nome}")
            
            # Criar estoques
            mao_qty = limpar_numero(row.get('MAO')) or 0
            sp_qty = limpar_numero(row.get('SP')) or 0
            
            if mao_qty > 0:
                ProductStock.objects.update_or_create(
                    product=produto,
                    location='MAO',
                    defaults={'quantity': mao_qty}
                )
                stocks_criados += 1
            
            if sp_qty > 0:
                ProductStock.objects.update_or_create(
                    product=produto,
                    location='SP',
                    defaults={'quantity': sp_qty}
                )
                stocks_criados += 1
                
        except Exception as e:
            print(f"✗ Erro linha {idx + 2}: {str(e)}")
    
    print(f"\n📊 Produtos: {produtos_criados} | Estoques: {stocks_criados}")
    return produtos_criados

def importar_clientes(arquivo):
    """Importa clientes da aba CLIENTES"""
    print("\n" + "="*60)
    print("👥 IMPORTANDO CLIENTES")
    print("="*60)
    
    df = pd.read_excel(arquivo, sheet_name='CLIENTES', skiprows=1)
    
    clientes_criados = 0
    clientes_nomes = []
    
    for col in df.columns[1:]:
        nome = limpar_texto(df[col].iloc[0])
        if nome and nome != 'CLIENTES':
            clientes_nomes.append(nome)
    
    for nome in clientes_nomes:
        try:
            cliente, criado = Client.objects.get_or_create(name=nome)
            if criado:
                clientes_criados += 1
                print(f"✓ {nome}")
        except Exception as e:
            print(f"✗ Erro: {str(e)}")
    
    print(f"\n📊 Clientes criados: {clientes_criados}")
    return clientes_criados

def importar_entradas(arquivo):
    """Importa entradas da aba ENTRADA"""
    print("\n" + "="*60)
    print("📥 IMPORTANDO ENTRADAS")
    print("="*60)
    
    # Pegar primeiro usuário
    usuario = Employee.objects.first()
    if not usuario:
        print("❌ ERRO: Crie um superusuário primeiro!")
        print("   docker compose exec web python manage.py createsuperuser")
        return 0
    
    df = pd.read_excel(arquivo, sheet_name='ENTRADA', skiprows=3)
    
    colunas = ['DATA', 'PRODUTO', 'FABRICANTE', 'MODELO', 
               'ARMAZEM', 'FORNECEDOR', 'QUEM_RECEBEU', 'NF', 'QTD']
    df.columns = colunas[:len(df.columns)]
    
    entradas_criadas = 0
    entradas_puladas = 0
    
    for idx, row in df.iterrows():
        try:
            nome = limpar_texto(row.get('PRODUTO'))
            if not nome:
                continue
            
            # Buscar ou criar produto
            try:
                produto = Product.objects.get(name=nome)
            except Product.DoesNotExist:
                produto = Product.objects.create(
                    name=nome,
                    manufacturer=limpar_texto(row.get('FABRICANTE')) or '',
                    model=limpar_texto(row.get('MODELO')) or ''
                )
            
            quantidade = limpar_numero(row.get('QTD'))
            if not quantidade or quantidade <= 0:
                continue
            
            armazem = limpar_texto(row.get('ARMAZEM')) or 'MAO'
            if armazem.upper() not in ['MAO', 'SP']:
                armazem = 'MAO'
            else:
                armazem = armazem.upper()
            
            nf = limpar_texto(row.get('NF')) or ''
            
            # Verificar se NF + produto já existe
            if nf and StockEntry.objects.filter(nf_number=nf, product=produto).exists():
                entradas_puladas += 1
                continue
            
            # Criar entrada (NÃO cria estoque, o save() do modelo faz isso!)
            StockEntry.objects.create(
                product=produto,
                quantity=quantidade,
                location=armazem,
                entry_type='COMPRA',
                nf_number=nf,
                employee=usuario
            )
            
            entradas_criadas += 1
            print(f"✓ {nome} - {quantidade}un ({armazem})")
                
        except Exception as e:
            print(f"✗ Erro linha {idx + 4}: {str(e)}")
    
    print(f"\n📊 Entradas: {entradas_criadas} | Puladas: {entradas_puladas}")
    return entradas_criadas

def importar_saidas(arquivo):
    """Importa saídas da aba SAÍDA"""
    print("\n" + "="*60)
    print("📤 IMPORTANDO SAÍDAS")
    print("="*60)
    
    # Pegar primeiro usuário
    usuario = Employee.objects.first()
    if not usuario:
        print("❌ ERRO: Crie um superusuário primeiro!")
        return 0
    
    try:
        # Linha 4 tem o cabeçalho, então pular as 4 primeiras
        df = pd.read_excel(arquivo, sheet_name='SAÍDA', skiprows=4)
    except Exception as e:
        print(f"⚠️ Erro ao ler aba SAÍDA: {e}")
        return 0
    
    # Renomear colunas (remover espaços extras)
    df.columns = [str(col).strip() for col in df.columns]
    
    print(f"Colunas encontradas: {list(df.columns)[:10]}")
    
    saidas_criadas = 0
    saidas_puladas = 0
    
    for idx, row in df.iterrows():
        try:
            nome_produto = limpar_texto(row.get('PRODUTO'))
            nome_cliente = limpar_texto(row.get('CLIENTE'))
            
            if not nome_produto or not nome_cliente:
                continue
            
            # Buscar produto
            try:
                produto = Product.objects.get(name__iexact=nome_produto)
            except Product.DoesNotExist:
                print(f"⚠️ Produto não encontrado: {nome_produto}")
                continue
            
            # Buscar cliente
            try:
                cliente = Client.objects.get(name__iexact=nome_cliente)
            except Client.DoesNotExist:
                # Criar cliente se não existir
                cliente = Client.objects.create(name=nome_cliente)
                print(f"  → Cliente criado: {nome_cliente}")
            
            quantidade = limpar_numero(row.get('QTD'))
            if not quantidade or quantidade <= 0:
                continue
            
            armazem = limpar_texto(row.get('LOCAL')) or 'MAO'
            if armazem.upper() not in ['MAO', 'SP']:
                armazem = 'MAO'
            else:
                armazem = armazem.upper()
            
            tipo_saida = limpar_texto(row.get('TIPO DE SAÍDA')) or 'SAIDA'
            
            # Mapear tipo
            tipo_map = {
                'DEFINITIVO': 'SAIDA',
                'EMPRESTIMO': 'EMPRESTIMO',
                'RESERVA': 'RESERVA',
                'DESCARTE': 'DESCARTE'
            }
            movement_type = tipo_map.get(tipo_saida.upper(), 'SAIDA')
            
            # Verificar se tem estoque suficiente
            stock = ProductStock.objects.filter(
                product=produto,
                location=armazem
            ).first()
            
            if not stock or stock.quantity < quantidade:
                print(f"⚠️ Estoque insuficiente: {nome_produto} em {armazem} (tem {stock.quantity if stock else 0}, precisa {quantidade})")
                saidas_puladas += 1
                continue
            
            # Criar saída
            from core.models import StockOut
            StockOut.objects.create(
                product=produto,
                client=cliente,
                quantity=quantidade,
                location=armazem,
                movement_type=movement_type,
                employee=usuario
            )
            
            saidas_criadas += 1
            if saidas_criadas <= 10:  # Mostrar só as primeiras 10
                print(f"✓ {nome_produto} → {nome_cliente} ({quantidade}un em {armazem})")
                
        except Exception as e:
            print(f"✗ Erro linha {idx + 5}: {str(e)}")
    
    print(f"\n📊 Saídas criadas: {saidas_criadas} | Puladas: {saidas_puladas}")
    return saidas_criadas

def main():
    arquivo = 'ESTOQUE_CLEARIT_TESTE_MELHORIAS.xlsx'
    
    print("\n" + "="*60)
    print("🚀 MIGRAÇÃO DE DADOS - EXCEL → BANCO")
    print("="*60)
    
    try:
        prod = importar_produtos(arquivo)
        cli = importar_clientes(arquivo)
        ent = importar_entradas(arquivo)
        sai = importar_saidas(arquivo)
        
        print("\n" + "="*60)
        print("✅ MIGRAÇÃO CONCLUÍDA!")
        print("="*60)
        print(f"📦 Produtos: {prod}")
        print(f"👥 Clientes: {cli}")
        print(f"📥 Entradas: {ent}")
        print(f"📤 Saídas: {sai}")
        
    except Exception as e:
        print(f"\n❌ ERRO: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()