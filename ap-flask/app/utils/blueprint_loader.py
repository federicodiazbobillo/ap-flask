# app/utils/blueprint_loader.py

import os
import importlib
from flask import Blueprint

def register_blueprints(app, base_package, base_path):
    for root, _, files in os.walk(base_path):
        for file in files:
            if file.endswith('.py') and not file.startswith('__'):
                rel_path = os.path.relpath(os.path.join(root, file), base_path)
                module_path = f"{base_package}." + rel_path.replace(os.path.sep, '.').replace('.py', '')

                try:
                    module = importlib.import_module(module_path)
                    for item in dir(module):
                        obj = getattr(module, item)
                        if isinstance(obj, Blueprint):
                            app.register_blueprint(obj)
                except Exception as e:
                    print(f"❌ Error al registrar blueprint {module_path}: {e}")
