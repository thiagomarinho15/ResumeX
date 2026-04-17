from app import app, db
from app.models import Role, User
from app.security import hash_password

with app.app_context():
    # Roles
    for role_name, description in [
        ("admin", "Administrador do sistema"),
        ("usuario", "Usuário comum"),
    ]:
        if not Role.query.filter_by(name=role_name).first():
            db.session.add(Role(name=role_name, description=description))
    db.session.commit()

    # Admin user
    if not User.query.filter_by(email="admin@resumex.com").first():
        admin_role = Role.query.filter_by(name="admin").first()
        admin = User(
            nome="Admin",
            email="admin@resumex.com",
            senha=hash_password("admin123"),
        )
        admin.roles.append(admin_role)
        db.session.add(admin)
        db.session.commit()
        print("✓ Admin criado: admin@resumex.com / admin123")
    else:
        print("Admin já existe.")
