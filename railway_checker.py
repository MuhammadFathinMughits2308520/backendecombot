#!/usr/bin/env python3
"""
Complete Django Railway Deployment Checker
Comprehensive validation for production deployment
"""

import os
import sys
import re
from pathlib import Path
from typing import Tuple, List, Dict

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")

def print_section(text):
    print(f"\n{Colors.BOLD}{text}{Colors.END}")
    print("-" * 70)

def check_status(passed: bool, message: str, fix: str = None):
    status = f"{Colors.GREEN}✅{Colors.END}" if passed else f"{Colors.RED}❌{Colors.END}"
    print(f"{status} {message}")
    if not passed and fix:
        print(f"   {Colors.YELLOW}💡 Fix: {fix}{Colors.END}")

def check_file_exists(filepath: str) -> Tuple[bool, str]:
    """Check if file exists"""
    path = Path(filepath)
    return path.exists(), str(path.absolute())

def read_file_safe(filepath: str) -> str:
    """Read file with multiple encoding attempts"""
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return ""

def check_requirements_txt():
    """Check requirements.txt thoroughly"""
    print_section("📦 Checking requirements.txt")
    
    exists, path = check_file_exists("requirements.txt")
    check_status(exists, "requirements.txt exists", 
                 "Create requirements.txt file")
    
    if not exists:
        return False
    
    content = read_file_safe("requirements.txt")
    
    # Critical dependencies
    critical_deps = {
        'django': 'Django>=4.2',
        'gunicorn': 'gunicorn==21.2.0',
        'whitenoise': 'whitenoise==6.6.0',
        'psycopg2': 'psycopg2-binary==2.9.9'
    }
    
    # Common dependencies
    recommended_deps = {
        'djangorestframework': 'djangorestframework>=3.14.0',
        'django-cors-headers': 'django-cors-headers>=4.3.0',
        'python-decouple': 'python-decouple>=3.8',
        'pillow': 'Pillow>=10.0.0 (if using ImageField)',
    }
    
    print("\n  Critical Dependencies:")
    all_critical = True
    for dep, install_cmd in critical_deps.items():
        found = dep.lower() in content.lower() or (dep == 'psycopg2' and 'psycopg2-binary' in content.lower())
        check_status(found, f"{dep}", f"Add: {install_cmd}")
        if not found:
            all_critical = False
    
    print("\n  Recommended Dependencies:")
    for dep, install_cmd in recommended_deps.items():
        found = dep.lower() in content.lower()
        status = f"{Colors.GREEN}✓{Colors.END}" if found else f"{Colors.YELLOW}○{Colors.END}"
        print(f"  {status} {dep}")
    
    return all_critical

def check_django_settings():
    """Check Django settings.py comprehensively"""
    print_section("⚙️  Checking Django Settings")
    
    settings_paths = [
        "backend/settings.py",
        "settings.py", 
        "config/settings.py",
        "core/settings.py",
        "*/settings.py"
    ]
    
    settings_file = None
    for pattern in settings_paths:
        if '*' in pattern:
            matches = list(Path('.').glob(pattern))
            if matches:
                settings_file = str(matches[0])
                break
        else:
            if Path(pattern).exists():
                settings_file = pattern
                break
    
    if not settings_file:
        check_status(False, "settings.py found", "Create Django settings file")
        return False
    
    print(f"  📁 Found: {settings_file}")
    content = read_file_safe(settings_file)
    
    # Check critical settings
    checks = [
        ('SECRET_KEY', 'os.environ' in content or 'env(' in content, 
         "Use environment variable: SECRET_KEY = os.environ.get('SECRET_KEY')"),
        
        ('DEBUG', 'DEBUG = False' in content or "os.environ.get('DEBUG'" in content,
         "Set: DEBUG = os.environ.get('DEBUG', 'False') == 'True'"),
        
        ('ALLOWED_HOSTS', 'ALLOWED_HOSTS' in content,
         "Add: ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')"),
        
        ('Database', 'DATABASES' in content,
         "Configure DATABASES with environment variables"),
        
        ('Static Files', 'STATIC_URL' in content and 'STATIC_ROOT' in content,
         "Add: STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')"),
        
        ('WhiteNoise', 'whitenoise' in content.lower(),
         "Add 'whitenoise.middleware.WhiteNoiseMiddleware' to MIDDLEWARE"),
        
        ('CSRF Trusted', 'CSRF_TRUSTED_ORIGINS' in content or 'railway' in content.lower(),
         "Add: CSRF_TRUSTED_ORIGINS = ['https://*.railway.app']"),
    ]
    
    print("\n  Configuration Checks:")
    all_passed = True
    for name, passed, fix in checks:
        check_status(passed, name, fix if not passed else None)
        if not passed:
            all_passed = False
    
    return all_passed

def check_wsgi():
    """Check WSGI configuration"""
    print_section("🌐 Checking WSGI Configuration")
    
    wsgi_paths = [
        "backend/wsgi.py",
        "wsgi.py",
        "config/wsgi.py",
        "core/wsgi.py"
    ]
    
    wsgi_file = None
    for path in wsgi_paths:
        if Path(path).exists():
            wsgi_file = path
            break
    
    check_status(wsgi_file is not None, "wsgi.py found", 
                 "Create wsgi.py file")
    
    if wsgi_file:
        content = read_file_safe(wsgi_file)
        check_status('get_wsgi_application' in content, 
                    "WSGI application configured",
                    "Ensure get_wsgi_application() is called")
    
    return wsgi_file is not None

def check_env_example():
    """Check environment variables template"""
    print_section("🔐 Checking Environment Variables")
    
    exists, _ = check_file_exists(".env.example")
    check_status(exists, ".env.example exists (documentation)",
                 "Create .env.example with required variables")
    
    if exists:
        content = read_file_safe(".env.example")
        required_vars = ['SECRET_KEY', 'DEBUG', 'DATABASE_URL', 'ALLOWED_HOSTS']
        
        print("\n  Required Variables:")
        for var in required_vars:
            found = var in content
            check_status(found, var, f"Add {var}=your_value")

def check_gitignore():
    """Check .gitignore"""
    print_section("🔒 Checking .gitignore")
    
    exists, _ = check_file_exists(".gitignore")
    check_status(exists, ".gitignore exists",
                 "Create .gitignore file")
    
    if exists:
        content = read_file_safe(".gitignore")
        critical_ignores = ['.env', '__pycache__', '*.pyc', 'db.sqlite3', 'staticfiles/']
        
        print("\n  Critical Entries:")
        for entry in critical_ignores:
            found = entry in content
            check_status(found, entry, f"Add '{entry}' to .gitignore")

def check_railway_config():
    """Check Railway specific files"""
    print_section("🚂 Checking Railway Configuration")
    
    # Check Procfile or railway.json
    procfile, _ = check_file_exists("Procfile")
    railway_json, _ = check_file_exists("railway.json")
    railway_toml, _ = check_file_exists("railway.toml")
    
    has_config = procfile or railway_json or railway_toml
    
    if procfile:
        content = read_file_safe("Procfile")
        has_web = 'web:' in content and 'gunicorn' in content
        check_status(has_web, "Procfile web command configured",
                    "Add: web: gunicorn backend.wsgi:application --bind 0.0.0.0:$PORT")
    else:
        print(f"  {Colors.YELLOW}ℹ️  No Procfile (Railway will use default command){Colors.END}")
    
    # Check runtime
    runtime, _ = check_file_exists("runtime.txt")
    if runtime:
        content = read_file_safe("runtime.txt")
        check_status('python-3' in content, "Python version specified",
                    "Add: python-3.11.x")

def check_database_config():
    """Check database configuration"""
    print_section("🗄️  Checking Database Configuration")
    
    settings_paths = ["backend/settings.py", "settings.py", "config/settings.py"]
    settings_file = None
    
    for path in settings_paths:
        if Path(path).exists():
            settings_file = path
            break
    
    if settings_file:
        content = read_file_safe(settings_file)
        
        checks = [
            ('DATABASE_URL', 'dj_database_url' in content or 'DATABASE_URL' in content,
             "Install dj-database-url and use: DATABASES['default'] = dj_database_url.parse(os.environ.get('DATABASE_URL'))"),
            
            ('PostgreSQL', 'postgresql' in content or 'psycopg2' in content or 'postgres' in content,
             "Configure PostgreSQL for production"),
        ]
        
        for name, passed, fix in checks:
            check_status(passed, name, fix if not passed else None)

def generate_fixes():
    """Generate comprehensive fix guide"""
    print_header("🔧 COMPLETE FIX GUIDE")
    
    print(f"\n{Colors.BOLD}1. Update requirements.txt{Colors.END}")
    print("   Add these lines:")
    print("""
   Django>=4.2,<5.0
   gunicorn==21.2.0
   whitenoise==6.6.0
   psycopg2-binary==2.9.9
   djangorestframework>=3.14.0
   django-cors-headers>=4.3.0
   python-decouple>=3.8
   dj-database-url>=2.1.0
    """)
    
    print(f"\n{Colors.BOLD}2. Update settings.py{Colors.END}")
    print("""
   import os
   from pathlib import Path
   
   # Security
   SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here')
   DEBUG = os.environ.get('DEBUG', 'False') == 'True'
   ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
   
   # CSRF for Railway
   CSRF_TRUSTED_ORIGINS = [
       'https://*.railway.app',
       'https://*.up.railway.app',
   ]
   
   # Middleware (add WhiteNoise after SecurityMiddleware)
   MIDDLEWARE = [
       'django.middleware.security.SecurityMiddleware',
       'whitenoise.middleware.WhiteNoiseMiddleware',  # Add this
       # ... rest of middleware
   ]
   
   # Static files
   STATIC_URL = '/static/'
   STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
   STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
   
   # Database (add this for Railway PostgreSQL)
   import dj_database_url
   DATABASES = {
       'default': dj_database_url.parse(
           os.environ.get('DATABASE_URL', 'sqlite:///db.sqlite3')
       )
   }
    """)
    
    print(f"\n{Colors.BOLD}3. Create/Update .gitignore{Colors.END}")
    print("""
   .env
   __pycache__/
   *.pyc
   *.pyo
   db.sqlite3
   staticfiles/
   media/
   .venv/
   venv/
   *.log
    """)
    
    print(f"\n{Colors.BOLD}4. Railway Configuration{Colors.END}")
    print("""
   In Railway Dashboard:
   
   Variables:
   - SECRET_KEY=your-secret-key-here
   - DEBUG=False
   - ALLOWED_HOSTS=your-app.railway.app
   - DJANGO_SETTINGS_MODULE=backend.settings
   
   Settings:
   - Build Command: pip install -r requirements.txt
   - Start Command: gunicorn backend.wsgi:application --bind 0.0.0.0:$PORT
   
   Or create Procfile:
   web: gunicorn backend.wsgi:application --bind 0.0.0.0:$PORT
    """)
    
    print(f"\n{Colors.BOLD}5. Deploy Steps{Colors.END}")
    print("""
   1. Make sure all files are saved
   2. Run: python manage.py collectstatic --noinput
   3. Commit changes:
      git add .
      git commit -m "fix: production configuration"
      git push
   4. Railway will auto-deploy
   5. Run migrations in Railway:
      python manage.py migrate
    """)

def main():
    print_header("🚀 Complete Django Railway Deployment Checker")
    
    print(f"\n{Colors.YELLOW}Running comprehensive checks...{Colors.END}")
    
    results = {
        'requirements': check_requirements_txt(),
        'settings': check_django_settings(),
        'wsgi': check_wsgi(),
        'env': check_env_example(),
        'gitignore': check_gitignore(),
        'railway': check_railway_config(),
        'database': check_database_config(),
    }
    
    generate_fixes()
    
    # Summary
    print_header("📊 SUMMARY")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\nChecks Passed: {passed}/{total}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✨ All checks passed! Ready to deploy! 🚀{Colors.END}")
    else:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  Please fix the issues above before deploying{Colors.END}")
    
    print(f"\n{Colors.BLUE}💡 Tip: Review the FIX GUIDE section above for detailed instructions{Colors.END}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Checker interrupted by user{Colors.END}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.END}")
        sys.exit(1)