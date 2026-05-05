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
                f'يمكن لفاحص مساعدتك في إنشاء اختبار مبدئي من هذا المصدر. {source_note}'
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
            'message': 'صدى غير متوفر حاليًا. قريبًا سيساعدك في المحاضرات الصوتية.',
        },
    }
