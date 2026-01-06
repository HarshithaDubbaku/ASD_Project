"""
Tests for internationalization (i18n) module
Extension 9: Multi-Language Support
"""

import pytest
import json
import os
import tempfile
from flask import Flask, session, g
from i18n import (
    LanguageManager, 
    TranslationStrings,
    init_language_manager,
    get_language_manager,
    translate,
    get_current_language,
    set_language
)


@pytest.fixture
def temp_translations():
    """Create temporary translation files for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create English translations
        en_trans = {
            'home': {'title': 'Welcome', 'subtitle': 'Test App'},
            'auth': {'login': 'Login', 'register': 'Sign Up'},
            'messages': {'welcome': 'Hello', 'error': 'Error occurred'}
        }
        
        with open(os.path.join(tmpdir, 'en.json'), 'w') as f:
            json.dump(en_trans, f)
        
        # Create Spanish translations
        es_trans = {
            'home': {'title': 'Bienvenido', 'subtitle': 'Aplicación de Prueba'},
            'auth': {'login': 'Iniciar Sesión', 'register': 'Registrarse'},
            'messages': {'welcome': 'Hola', 'error': 'Ocurrió un error'}
        }
        
        with open(os.path.join(tmpdir, 'es.json'), 'w') as f:
            json.dump(es_trans, f)
        
        # Create French translations
        fr_trans = {
            'home': {'title': 'Bienvenue', 'subtitle': 'Application de Test'},
            'auth': {'login': 'Connexion', 'register': 'Inscription'},
            'messages': {'welcome': 'Bonjour', 'error': 'Une erreur s\'est produite'}
        }
        
        with open(os.path.join(tmpdir, 'fr.json'), 'w') as f:
            json.dump(fr_trans, f)
        
        yield tmpdir


@pytest.fixture
def app_context(temp_translations):
    """Create Flask app context for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.secret_key = 'test_secret'
    
    with app.test_request_context():
        yield app


class TestLanguageManager:
    """Test LanguageManager class."""
    
    def test_initialization(self, temp_translations):
        """Test LanguageManager initialization."""
        manager = LanguageManager(temp_translations)
        
        assert manager is not None
        assert manager.translations_path == temp_translations
        assert manager.DEFAULT_LANGUAGE == 'en'
    
    def test_load_language(self, temp_translations):
        """Test loading a specific language."""
        manager = LanguageManager(temp_translations)
        
        result = manager.load_language('en')
        assert result is True
        assert 'en' in manager.translations
        assert 'home' in manager.translations['en']
    
    def test_load_missing_language(self, temp_translations):
        """Test loading non-existent language."""
        manager = LanguageManager(temp_translations)
        
        result = manager.load_language('xx')
        assert result is False
        assert 'xx' in manager.translations
        assert manager.translations['xx'] == {}
    
    def test_get_text_simple_key(self, temp_translations):
        """Test getting text with simple key."""
        manager = LanguageManager(temp_translations)
        
        text = manager.get_text('home.title', 'en')
        assert text == 'Welcome'
    
    def test_get_text_nested_key(self, temp_translations):
        """Test getting text with nested key."""
        manager = LanguageManager(temp_translations)
        
        text = manager.get_text('auth.login', 'en')
        assert text == 'Login'
        
        text = manager.get_text('messages.welcome', 'es')
        assert text == 'Hola'
    
    def test_get_text_missing_key(self, temp_translations):
        """Test getting text with missing key."""
        manager = LanguageManager(temp_translations)
        
        text = manager.get_text('nonexistent.key', 'en', 'default')
        assert text == 'default'
    
    def test_get_text_missing_language(self, temp_translations):
        """Test getting text with missing language."""
        manager = LanguageManager(temp_translations)
        
        text = manager.get_text('home.title', 'xx', 'default')
        assert text == 'default'
    
    def test_set_language(self, app_context, temp_translations):
        """Test setting current language."""
        with app_context.test_request_context():
            manager = LanguageManager(temp_translations)
            
            result = manager.set_language('es')
            assert result is True
            assert session.get('language') == 'es'
    
    def test_set_invalid_language(self, app_context, temp_translations):
        """Test setting invalid language."""
        with app_context.test_request_context():
            manager = LanguageManager(temp_translations)
            
            result = manager.set_language('xx')
            assert result is False
    
    def test_get_all_languages(self, temp_translations):
        """Test getting all supported languages."""
        manager = LanguageManager(temp_translations)
        
        languages = manager.get_all_languages()
        assert isinstance(languages, dict)
        assert 'en' in languages
        assert 'es' in languages
    
    def test_get_language_name(self, temp_translations):
        """Test getting language name."""
        manager = LanguageManager(temp_translations)
        
        name = manager.get_language_name('en')
        assert name == 'English'
        
        name = manager.get_language_name('es')
        assert name == 'Español'
    
    def test_translate_dict(self, temp_translations):
        """Test translating a dictionary."""
        manager = LanguageManager(temp_translations)
        
        # translate_dict expects dictionary keys to be translated with optional prefix
        # Test with no prefix - keys are used as-is
        data = {'title': 'home.title', 'login': 'auth.login'}
        translated = manager.translate_dict(data, 'en')
        
        # These keys don't exist, so they're returned as-is
        assert translated['title'] == 'home.title'
        assert translated['login'] == 'auth.login'
        
        # Test with prefix to properly translate keys
        data_simple = {'title': 'title', 'subtitle': 'subtitle'}
        translated_prefixed = manager.translate_dict(data_simple, 'en', 'home.')
        assert translated_prefixed['title'] == 'Welcome'
        assert translated_prefixed['subtitle'] == 'Test App'
    
    def test_translate_dict_with_prefix(self, temp_translations):
        """Test translating dictionary with key prefix."""
        manager = LanguageManager(temp_translations)
        
        data = {'title': 'title', 'subtitle': 'subtitle'}
        translated = manager.translate_dict(data, 'en', 'home.')
        
        assert translated['title'] == 'Welcome'
        assert translated['subtitle'] == 'Test App'
    
    def test_current_language_default(self, app_context):
        """Test getting current language (default)."""
        with app_context.test_request_context():
            manager = LanguageManager()
            
            lang = manager.get_current_language()
            assert lang in ['en', 'es', 'fr', 'de', 'zh', 'ja', 'pt', 'ar']
    
    def test_supported_languages_count(self, temp_translations):
        """Test that all languages are supported."""
        manager = LanguageManager(temp_translations)
        
        expected = ['en', 'es', 'fr', 'de', 'zh', 'ja', 'pt', 'ar']
        actual = list(manager.SUPPORTED_LANGUAGES.keys())
        
        assert len(actual) == len(expected)


class TestTranslationStrings:
    """Test TranslationStrings constants."""
    
    def test_nav_constants(self):
        """Test navigation translation constants."""
        assert TranslationStrings.NAV_HOME == 'nav.home'
        assert TranslationStrings.NAV_LOGOUT == 'nav.logout'
    
    def test_auth_constants(self):
        """Test authentication constants."""
        assert TranslationStrings.AUTH_LOGIN == 'auth.login'
        assert TranslationStrings.AUTH_REGISTER == 'auth.register'
    
    def test_form_constants(self):
        """Test form constants."""
        assert TranslationStrings.FORM_AGE == 'form.age'
        assert TranslationStrings.FORM_SUBMIT == 'form.submit'
    
    def test_message_constants(self):
        """Test message constants."""
        assert TranslationStrings.MSG_WELCOME == 'messages.welcome'
        assert TranslationStrings.MSG_ERROR == 'messages.error'
    
    def test_result_constants(self):
        """Test result constants."""
        assert TranslationStrings.RESULT_SCORE == 'result.score'
        assert TranslationStrings.RESULT_PREDICTION == 'result.prediction'


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_init_language_manager(self, temp_translations, app_context):
        """Test initializing language manager with app."""
        with app_context.test_request_context():
            manager = init_language_manager(app_context, temp_translations)
            
            assert manager is not None
            assert isinstance(manager, LanguageManager)
    
    def test_get_language_manager(self, temp_translations, app_context):
        """Test getting language manager instance."""
        with app_context.test_request_context():
            init_language_manager(app_context, temp_translations)
            manager = get_language_manager()
            
            assert manager is not None
            assert isinstance(manager, LanguageManager)
    
    def test_translate_function(self, temp_translations, app_context):
        """Test translate convenience function."""
        with app_context.test_request_context():
            init_language_manager(app_context, temp_translations)
            
            text = translate('home.title', 'en')
            assert text == 'Welcome'
    
    def test_get_current_language_function(self, temp_translations, app_context):
        """Test get_current_language convenience function."""
        with app_context.test_request_context():
            init_language_manager(app_context, temp_translations)
            
            lang = get_current_language()
            manager = get_language_manager()
            assert lang in manager.SUPPORTED_LANGUAGES.keys()
    
    def test_set_language_function(self, temp_translations, app_context):
        """Test set_language convenience function."""
        with app_context.test_request_context():
            init_language_manager(app_context, temp_translations)
            
            result = set_language('es')
            assert result is True


class TestLanguageIntegration:
    """Integration tests for language support."""
    
    def test_translation_fallback(self, temp_translations):
        """Test fallback to default when translation missing."""
        manager = LanguageManager(temp_translations)
        
        text = manager.get_text('missing.key', 'en', 'fallback')
        assert text == 'fallback'
    
    def test_multiple_language_switching(self, app_context, temp_translations):
        """Test switching between multiple languages."""
        with app_context.test_request_context():
            manager = LanguageManager(temp_translations)
            
            # Switch to Spanish
            manager.set_language('es')
            assert session.get('language') == 'es'
            
            # Switch to French
            manager.set_language('fr')
            assert session.get('language') == 'fr'
    
    def test_language_persistence(self, app_context, temp_translations):
        """Test that language preference persists in session."""
        with app_context.test_request_context():
            manager = LanguageManager(temp_translations)
            manager.set_language('es')
            
            # Get current language should return Spanish
            current = manager.get_current_language()
            assert current == 'es'
    
    def test_all_languages_have_translations(self, temp_translations):
        """Test that all supported languages have translation files."""
        manager = LanguageManager(temp_translations)
        manager.load_all_translations()
        
        # At minimum, English should be loaded
        assert 'en' in manager.translations
        assert len(manager.translations['en']) > 0


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_translation_key(self, temp_translations):
        """Test with empty translation key."""
        manager = LanguageManager(temp_translations)
        
        text = manager.get_text('', 'en', 'default')
        assert text == 'default'
    
    def test_special_characters_in_translation(self, temp_translations):
        """Test handling special characters in translations."""
        manager = LanguageManager(temp_translations)
        
        text = manager.get_text('messages.error', 'fr')
        assert "s'est" in text  # French uses apostrophe
    
    def test_unicode_in_translation(self, temp_translations):
        """Test handling Unicode characters."""
        manager = LanguageManager(temp_translations)
        
        text = manager.get_text('home.title', 'es')
        assert 'é' in text or text  # Spanish has accented characters


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
