"""
Multi-Language Support Module
Extension 9: Internationalization (i18n) framework
"""

import json
import os
from typing import Dict, List, Optional, Any
from flask import session, request, g


class LanguageManager:
    """Manage multi-language support for the application."""
    
    # Supported languages
    SUPPORTED_LANGUAGES = {
        'en': 'English',
        'es': 'Español',
        'fr': 'Français',
        'de': 'Deutsch',
        'zh': '中文',
        'ja': '日本語',
        'pt': 'Português',
        'ar': 'العربية',
        'te': 'తెలుగు',
        'hi': 'हिन्दी',
    }
    
    DEFAULT_LANGUAGE = 'en'
    
    def __init__(self, translations_path: str = 'translations'):
        """
        Initialize language manager.
        
        Args:
            translations_path: Path to translations directory
        """
        self.translations_path = translations_path
        self.translations = {}
        self.load_all_translations()
    
    def load_all_translations(self) -> bool:
        """Load all available translations."""
        try:
            for lang_code in self.SUPPORTED_LANGUAGES.keys():
                self.load_language(lang_code)
            return True
        except Exception as e:
            print(f"Error loading translations: {e}")
            return False
    
    def load_language(self, lang_code: str) -> bool:
        """
        Load a specific language translation file.
        
        Args:
            lang_code: Language code (e.g., 'en', 'es')
            
        Returns:
            Success status
        """
        try:
            file_path = os.path.join(self.translations_path, f'{lang_code}.json')
            
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.translations[lang_code] = json.load(f)
                return True
            else:
                # Create empty translation dict for missing languages
                self.translations[lang_code] = {}
                return False
        except Exception as e:
            print(f"Error loading language {lang_code}: {e}")
            self.translations[lang_code] = {}
            return False
    
    def get_text(self, key: str, lang_code: Optional[str] = None, 
                 default: str = '') -> str:
        """
        Get translated text.
        
        Args:
            key: Translation key (e.g., 'home.title')
            lang_code: Language code (uses current if None)
            default: Default text if key not found
            
        Returns:
            Translated text or default
        """
        if lang_code is None:
            lang_code = self.get_current_language()
        
        try:
            # Support nested keys (e.g., 'home.title' -> dict['home']['title'])
            keys = key.split('.')
            value = self.translations.get(lang_code, {})
            
            for k in keys:
                if isinstance(value, dict):
                    value = value.get(k)
                else:
                    return default
            
            return str(value) if value is not None else default
        except Exception:
            return default
    
    def get_current_language(self) -> str:
        """
        Get current language code.
        
        Priority:
        1. Session language
        2. User preference from database
        3. Browser language
        4. Default language
        
        Returns:
            Language code
        """
        # Check session
        if 'language' in session:
            return session['language']
        
        # Check browser language
        best_match = request.accept_languages.best_match(
            list(self.SUPPORTED_LANGUAGES.keys())
        )
        if best_match:
            return best_match
        
        return self.DEFAULT_LANGUAGE
    
    def set_language(self, lang_code: str) -> bool:
        """
        Set current language.
        
        Args:
            lang_code: Language code to set
            
        Returns:
            Success status
        """
        if lang_code in self.SUPPORTED_LANGUAGES:
            session['language'] = lang_code
            g.language = lang_code
            return True
        return False
    
    def get_all_languages(self) -> Dict[str, str]:
        """
        Get all supported languages.
        
        Returns:
            Dictionary of language codes and names
        """
        return self.SUPPORTED_LANGUAGES.copy()
    
    def get_language_name(self, lang_code: str) -> str:
        """
        Get human-readable language name.
        
        Args:
            lang_code: Language code
            
        Returns:
            Language name
        """
        return self.SUPPORTED_LANGUAGES.get(lang_code, lang_code)
    
    def translate_dict(self, data: Dict[str, str], lang_code: Optional[str] = None,
                       key_prefix: str = '') -> Dict[str, str]:
        """
        Translate all values in a dictionary.
        
        Args:
            data: Dictionary with translation keys as values
            lang_code: Language code
            key_prefix: Prefix for all keys (e.g., 'home.')
            
        Returns:
            Dictionary with translated values
        """
        translated = {}
        for k, v in data.items():
            if isinstance(v, str):
                full_key = f'{key_prefix}{k}' if key_prefix else k
                translated[k] = self.get_text(full_key, lang_code, v)
            else:
                translated[k] = v
        return translated


class TranslationStrings:
    """Pre-defined translation string keys."""
    
    # Navigation
    NAV_HOME = 'nav.home'
    NAV_NEW_TEST = 'nav.new_test'
    NAV_HISTORY = 'nav.history'
    NAV_LOGOUT = 'nav.logout'
    
    # Authentication
    AUTH_LOGIN = 'auth.login'
    AUTH_REGISTER = 'auth.register'
    AUTH_USERNAME = 'auth.username'
    AUTH_PASSWORD = 'auth.password'
    AUTH_EMAIL = 'auth.email'
    AUTH_LOGIN_BUTTON = 'auth.login_button'
    AUTH_REGISTER_BUTTON = 'auth.register_button'
    
    # Forms
    FORM_AGE = 'form.age'
    FORM_GENDER = 'form.gender'
    FORM_ETHNICITY = 'form.ethnicity'
    FORM_RELATION = 'form.relation'
    FORM_SUBMIT = 'form.submit'
    FORM_CANCEL = 'form.cancel'
    
    # Messages
    MSG_WELCOME = 'messages.welcome'
    MSG_LOGIN_SUCCESS = 'messages.login_success'
    MSG_LOGOUT_SUCCESS = 'messages.logout_success'
    MSG_ERROR = 'messages.error'
    MSG_NO_DATA = 'messages.no_data'
    
    # Results
    RESULT_SCORE = 'result.score'
    RESULT_PREDICTION = 'result.prediction'
    RESULT_CONFIDENCE = 'result.confidence'
    RESULT_HIGH_RISK = 'result.high_risk'
    RESULT_LOW_RISK = 'result.low_risk'
    
    # Settings
    SETTINGS_LANGUAGE = 'settings.language'
    SETTINGS_SAVE = 'settings.save'
    SETTINGS_CANCEL = 'settings.cancel'


# Global language manager instance
_language_manager: Optional[LanguageManager] = None


def init_language_manager(app, translations_path: str = 'translations') -> LanguageManager:
    """
    Initialize language manager with Flask app.
    
    Args:
        app: Flask application
        translations_path: Path to translations directory
        
    Returns:
        LanguageManager instance
    """
    global _language_manager
    
    _language_manager = LanguageManager(translations_path)
    
    # Register before_request hook
    @app.before_request
    def before_request():
        g.language = _language_manager.get_current_language()
        g.lang_manager = _language_manager
        g.t = _language_manager.get_text
    
    # Register template context processor
    @app.context_processor
    def inject_language_info():
        return {
            'current_language': _language_manager.get_current_language(),
            'supported_languages': _language_manager.get_all_languages(),
            'get_language_name': _language_manager.get_language_name,
            't': _language_manager.get_text,
        }
    
    return _language_manager


def get_language_manager() -> Optional[LanguageManager]:
    """Get the current language manager instance."""
    return _language_manager


def translate(key: str, lang_code: Optional[str] = None, default: str = '') -> str:
    """
    Convenience function to translate text.
    
    Args:
        key: Translation key
        lang_code: Language code
        default: Default text
        
    Returns:
        Translated text
    """
    if _language_manager:
        return _language_manager.get_text(key, lang_code, default)
    return default


def get_current_language() -> str:
    """
    Get current language code.
    
    Returns:
        Language code
    """
    if _language_manager:
        return _language_manager.get_current_language()
    return 'en'


def set_language(lang_code: str) -> bool:
    """
    Set current language.
    
    Args:
        lang_code: Language code
        
    Returns:
        Success status
    """
    if _language_manager:
        return _language_manager.set_language(lang_code)
    return False
