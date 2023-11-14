##### Deprecated features

- [ ] Change method to encrypt passwords:
  - user.password = generate_password_hash(new_password, method='sha256')
  - ```UserWarning: The 'sha256' password method is deprecated and will be removed in Werkzeug 3.0. Migrate to the 'scrypt' method.```
