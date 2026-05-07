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
    
    colunas = ['ITEM', 'PRODUTO', 'FABRICANTE', 'CATEGORIA', 'MODELO', 
               'MAO', 'SP', 'RJ', 'OUTROS', 'TOTAL', 'STATUS', 'OBS']
    df.columns = colunas[:len(df.columns)]
    
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

def main():
    arquivo = 'ESTOQUE_CLEARIT_TESTE_MELHORIAS.xlsx'
    
    print("\n" + "="*60)
    print("🚀 MIGRAÇÃO DE DADOS - EXCEL → BANCO")
    print("="*60)
    
    try:
        prod = importar_produtos(arquivo)
        cli = importar_clientes(arquivo)
        ent = importar_entradas(arquivo)
        
        print("\n" + "="*60)
        print("✅ MIGRAÇÃO CONCLUÍDA!")
        print("="*60)
        print(f"📦 Produtos: {prod}")
        print(f"👥 Clientes: {cli}")
        print(f"📥 Entradas: {ent}")
        
    except Exception as e:
        print(f"\n❌ ERRO: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()