FROM boky/postfix:latest

# Switch to root to override configs
USER root

# Install dependencies for catcher
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy our Postfix configs (overrides image defaults)
# Build context: mail-server/  (so paths are relative to that)
COPY postfix/main.cf /etc/postfix/main.cf
COPY postfix/master.cf /etc/postfix/master.cf
COPY postfix/virtual_regexp /etc/postfix/virtual_regexp

# Copy catcher script
COPY catcher/catcher.py /usr/local/bin/catcher.py
RUN chmod +x /usr/local/bin/catcher.py

# Ensure local user "tempmail" exists for catch-all delivery
RUN id -u tempmail >/dev/null 2>&1 || adduser --disabled-password --gecos "TempMail" --no-create-home tempmail

# Ensure /etc/aliases is a proper hash db (no NIS)
RUN postalias hash:/etc/aliases 2>/dev/null || newaliases || true

# Apply ALL critical postconf settings (bypass any entrypoint resets)
RUN postconf -e 'alias_maps=hash:/etc/aliases' && \
    postconf -e 'alias_database=hash:/etc/aliases' && \
    postconf -e 'local_recipient_maps=' && \
    postconf -e 'smtpd_recipient_restrictions=permit_mynetworks, reject_non_fqdn_recipient, reject_unknown_recipient_domain, reject_unauth_destination, permit' && \
    postconf -e 'compatibility_level=3.6'

# Expose SMTP
EXPOSE 25

# Override CMD to bypass boky/postfix entrypoint that resets configs
CMD ["postfix", "start-fg"]
