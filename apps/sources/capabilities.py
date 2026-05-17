from .models import StudentSource


def get_source_character_capabilities(source):
    supports_text = bool(source.extracted_text)
    source_note = (
        'النص المستخرج متوفر، لذلك يمكن تقديم تجربة أدق.'
        if supports_text
        else 'سيتم التعامل مع المصدر كمرفق دراسي دون تحليل محتواه الآن.'
    )

    khota_available = source.source_type != StudentSource.SourceType.AUDIO
    fahes_available = source.source_type != StudentSource.SourceType.AUDIO

    return {
        'khota': {
            'available': khota_available,
            'actions': ['create_study_plan'] if khota_available else [],
            'message': (
                f'يمكن لخُطى مساعدتك في تحويل هذا المصدر إلى خطة مذاكرة. {source_note}'
                if khota_available
                else 'خُطى لا تنشئ خطة من الملفات الصوتية في هذا الإصدار.'
            ),
        },
        'fahes': {
            'available': fahes_available,
            'actions': ['create_quiz'] if fahes_available else [],
            'message': (
                f'يمكن لفاحص إنشاء اختبار مبدئي من هذا المصدر. {source_note}'
                if fahes_available
                else 'فاحص لا ينشئ اختبارات من الملفات الصوتية في هذا الإصدار.'
            ),
        },
        'rasheed': {
            'available': True,
            'actions': ['study_advice'],
            'message': 'يمكن لرشيد إرشادك لطريقة مذاكرة هذا المصدر وربطه بخطتك الدراسية.',
        },
        'kholasa': {
            'available': False,
            'actions': [],
            'message': 'خلاصة غير متوفرة حاليًا. قريبًا ستساعدك في تلخيص مصادر الدراسة.',
        },
        'sada': {
            'available': False,
            'actions': [],
            'message': 'صدى غير متوفر حاليًا. قريبًا سيدعم المحاضرات الصوتية.',
        },
    }


def get_collection_character_capabilities(collection):
    sources = list(collection.sources.all())
    source_count = len(sources)
    has_sources = source_count > 0
    has_text = any(source.extracted_text for source in sources)
    has_unprocessed = any(not source.extracted_text for source in sources)

    if not has_sources:
        khota_message = 'أضف مصادر إلى هذا المجلد أولًا ليتم تحويله إلى خطة مذاكرة.'
        fahes_message = 'أضف مصادر إلى هذا المجلد أولًا ليتم إنشاء اختبار منه.'
    elif has_text:
        khota_message = 'يمكن لخُطى تحويل هذا المجلد إلى خطة مذاكرة.'
        fahes_message = 'يمكن لفاحص إنشاء اختبار أفضل من المصادر النصية الجاهزة داخل هذا المجلد.'
    elif has_unprocessed:
        khota_message = 'يمكن لخُطى إنشاء خطة عامة من مصادر هذا المجلد.'
        fahes_message = 'يمكن لفاحص إنشاء اختبار مسودة، لكن توليد الأسئلة يحتاج نصًا مستخرجًا لاحقًا.'
    else:
        khota_message = 'يمكن لخُطى تحويل هذا المجلد إلى خطة مذاكرة.'
        fahes_message = 'يمكن لفاحص إنشاء اختبار من مصادر هذا المجلد.'

    return {
        'khota': {
            'available': has_sources,
            'actions': ['create_study_plan'] if has_sources else [],
            'message': khota_message,
        },
        'fahes': {
            'available': has_sources,
            'actions': ['create_quiz'] if has_sources else [],
            'message': fahes_message,
        },
        'rasheed': {
            'available': True,
            'actions': ['study_advice'],
            'message': 'يمكن لرشيد إرشادك لتنظيم هذا المجلد.',
        },
        'kholasa': {
            'available': False,
            'actions': [],
            'message': 'خلاصة غير متوفرة حاليًا. قريبًا ستلخص لك المجلد.',
        },
        'sada': {
            'available': False,
            'actions': [],
            'message': 'صدى غير متوفر حاليًا. قريبًا سيدعم المحاضرات الصوتية.',
        },
    }
