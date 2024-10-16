from enum import Enum
from typing import List, Tuple, Dict

from django import forms


class AuthForm(forms.Form):
    """Form for entering client ID and client secret."""

    client_id: forms.CharField = forms.CharField(
        label='Client ID',
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'Введите Client ID'})
    )
    client_secret: forms.CharField = forms.CharField(
        label='Client Secret',
        max_length=100,
        widget=forms.PasswordInput(attrs={'placeholder': 'Введите Client Secret'})
    )


class TokenForm(forms.Form):
    """Form for entering the access code."""

    code: forms.CharField = forms.CharField(
        label='Код доступа',
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'Введите код доступа'})
    )


class FileType(str, Enum):
    """Enum of file types to filter."""

    ALL = 'Все'
    DOCUMENTS = 'Документы'
    IMAGES = 'Изображения'
    VIDEO = 'Видео'
    AUDIO = 'Аудио'

    def __str__(self) -> str:
        return self.value

    @classmethod
    def choices(cls) -> List[Tuple[str, str]]:
        """Returns a list of tuples for use in the select box."""
        return [(file_type, file_type) for file_type in cls]

    @classmethod
    def get_mime_prefix(cls, file_type_name: str) -> str:
        """Returns the MIME type prefix for the given file type."""
        mime_prefixes: Dict[str, str] = {
            cls.DOCUMENTS: 'application/',
            cls.IMAGES: 'image/',
            cls.VIDEO: 'video/',
            cls.AUDIO: 'audio/',
        }
        return mime_prefixes.get(file_type_name, "")


class PublicLinkForm(forms.Form):
    """Form for entering a public link to Yandex.Disk and selecting the file type."""

    public_key: forms.URLField = forms.URLField(
        label='Публичная ссылка на Яндекс.Диск',
        widget=forms.URLInput(attrs={'placeholder': 'Введите публичную ссылку'}),
    )
    file_type: forms.ChoiceField = forms.ChoiceField(
        label='Тип файлов',
        choices=FileType.choices(),
        required=False,
        initial=FileType.ALL.name,
        widget=forms.Select()
    )

    def clean_public_key(self) -> str:
        """Additional public link validation."""
        public_key: str = self.cleaned_data.get('public_key', '').strip()
        if not public_key.startswith('https://disk.yandex.ru/'):
            raise forms.ValidationError('Ссылка должна быть действительной публичной ссылкой Яндекс.Диска.')
        return public_key
