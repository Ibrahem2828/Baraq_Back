from .models import StudentSource


def get_source_character_capabilities(source):
    is_audio = source.source_type == StudentSource.SourceType.AUDIO
    return {
        'khota': {'available': not is_audio, 'actions': ['create_study_plan'] if not is_audio else [], 'message': 'تحويل المصدر إلى خطة دراسة ذكية.' if not is_audio else 'استخدم صدى أولًا لتحويل الصوت إلى نص.'},
        'fahes': {'available': not is_audio, 'actions': ['create_quiz'] if not is_audio else [], 'message': 'إنشاء اختبار موثق من المصدر.' if not is_audio else 'استخدم صدى أولًا لتحويل الصوت إلى نص.'},
        'rasheed': {'available': True, 'actions': ['study_advice'], 'message': 'تحليل الأداء وتقديم توصيات عملية.'},
        'kholasa': {'available': not is_audio, 'actions': ['summarize'] if not is_audio else [], 'message': 'إنشاء ملخص متعدد المستويات مع مراجع.' if not is_audio else 'استخدم صدى أولًا لتفريغ التسجيل.'},
        'sada': {'available': is_audio, 'actions': ['transcribe'] if is_audio else [], 'message': 'تحويل التسجيل الصوتي إلى نص منظم.' if is_audio else 'صدى مخصص للمصادر الصوتية.'},
    }


def get_collection_character_capabilities(collection):
    sources = list(collection.sources.all())
    has_sources = bool(sources)
    has_audio = any(source.source_type == StudentSource.SourceType.AUDIO for source in sources)
    return {
        'khota': {'available': has_sources, 'actions': ['create_study_plan'] if has_sources else [], 'message': 'إنشاء خطة من محتوى المجلد.' if has_sources else 'أضف مصادر أولًا.'},
        'fahes': {'available': has_sources, 'actions': ['create_quiz'] if has_sources else [], 'message': 'إنشاء اختبار من المجلد.' if has_sources else 'أضف مصادر أولًا.'},
        'rasheed': {'available': True, 'actions': ['study_advice'], 'message': 'تحليل الأداء المرتبط بالمجلد.'},
        'kholasa': {'available': has_sources, 'actions': ['summarize'] if has_sources else [], 'message': 'تلخيص مصادر المجلد.' if has_sources else 'أضف مصادر أولًا.'},
        'sada': {'available': has_audio, 'actions': ['transcribe'] if has_audio else [], 'message': 'تفريغ المصادر الصوتية داخل المجلد.' if has_audio else 'لا توجد مصادر صوتية.'},
    }
