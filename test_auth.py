import bcrypt

# Data yang ada di .env kamu
password_asli = "Benny@2025!"
hash_di_env = "$2b$12$k6PP5Svj6ndJOIrsCwZZuOrjZf0V1N55/7g4c1mvYA5x4jLiYO1lK"

print(f"--- DEBUG AUTH ---")
print(f"Password: {password_asli}")
print(f"Hash    : {hash_di_env}")

try:
    is_match = bcrypt.checkpw(password_asli.encode(), hash_di_env.encode())
    if is_match:
        print("\n✅ HASIL: COCOK! Password & Hash sudah benar.")
    else:
        print("\n❌ HASIL: TIDAK COCOK. Password atau Hash salah.")
except Exception as e:
    print(f"\n error: {e}")
