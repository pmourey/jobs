"""Parametres de tuning Ollama locaux pour cette machine.

Ces reglages visent un bon compromis latence/qualite sur un iMac
avec 16 CPU logiques et 64 Go de RAM, sans GPU dedie.
"""

IMAC_64GB_OLLAMA_TUNING = {
    'llama3.1:8b': {
        'options': {
            'num_thread': 16,
            'num_ctx': 1536,
        },
        'cv': {
            'max_tokens': 180,
            'request_timeout': 180,
        },
        'cover_letter': {
            'max_tokens': 160,
            'request_timeout': 210,
            'capture_excerpt_chars': 600,
            'existing_letter_excerpt_chars': 300,
        },
    },
}
