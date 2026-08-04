import ast
import os

with open('main.py', 'r', encoding='utf-8') as f:
    tree = ast.parse(f.read())

for node in ast.walk(tree):
    # Busca todas las importaciones que empiecen con 'actions.'
    if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith('actions.'):
        mod_name = node.module.split('.')[1]
        path = f'actions/{mod_name}.py'
        
        # Si el archivo no existe, lo crea con las funciones que main.py está pidiendo
        if not os.path.exists(path):
            with open(path, 'w', encoding='utf-8') as out:
                for alias in node.names:
                    out.write(f'def {alias.name}(*args, **kwargs):\n    return None\n\n')
print("✅ Todos los módulos faltantes han sido creados automáticamente.")
