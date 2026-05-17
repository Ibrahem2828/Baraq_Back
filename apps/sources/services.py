from collections import Counter
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.quizzes.models import (
    DifficultyLevelChoices,
    GenerationTypeChoices,
    Question,
    QuestionTypeChoices,
    Quiz,
    QuizStatusChoices,
    QuizTypeChoices,
)
from apps.study_plans.models import StudyPlan, StudyTask
from apps.study_plans.services import update_plan_completion

from .capabilities import (
    get_collection_character_capabilities,
    get_source_character_capabilities,
)
from .models import StudentSource, StudentSourceCollection, StudentSourceInteraction


TXT_READ_LIMIT_BYTES = 2 * 1024 * 1024


def process_source(source):
    source.status = StudentSource.Status.PROCESSING
    source.processing_error = ''
    source.save(update_fields=['status', 'processing_error', 'updated_at'])

    try:
        if source.source_type == StudentSource.SourceType.TEXT:
            source.extracted_text = _read_text_file(source)
            source.status = StudentSource.Status.READY
            source.metadata = {
                **(source.metadata or {}),
                'processing': 'txt_extracted',
                'processed_at': timezone.now().isoformat(),
            }
            message = 'تمت قراءة الملف النصي وحفظ محتواه للاستخدام داخل برّاق.'
        elif source.source_type == StudentSource.SourceType.AUDIO:
            source.status = StudentSource.Status.UPLOADED
            message = 'تم حفظ المصدر، والمعالجة المتقدمة لهذا النوع ستتوفر لاحقًا.'
        else:
            source.status = StudentSource.Status.UPLOADED
            message = 'تم حفظ المصدر، والمعالجة المتقدمة لهذا النوع ستتوفر لاحقًا.'

        source.processing_error = ''
        source.save(
            update_fields=[
                'status',
                'extracted_text',
                'processing_error',
                'metadata',
                'updated_at',
            ]
        )
        return {'success': True, 'message': message}
    except Exception as exc:
        source.status = StudentSource.Status.FAILED
        source.processing_error = str(exc)
        source.save(update_fields=['status', 'processing_error', 'updated_at'])
        return {
            'success': False,
            'message': 'فشلت معالجة المصدر. تأكد من أن الملف النصي صالح ثم حاول لاحقًا.',
            'error': str(exc),
        }


def _read_text_file(source):
    with source.file.open('rb') as file_obj:
        content = file_obj.read(TXT_READ_LIMIT_BYTES + 1)

    if len(content) > TXT_READ_LIMIT_BYTES:
        raise ValidationError('الملف النصي كبير جدًا للمعالجة الفورية.')

    for encoding in ('utf-8-sig', 'utf-8', 'cp1256', 'latin-1'):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise ValidationError('تعذر قراءة ترميز الملف النصي.')


def build_study_advice(source):
    common = [
        'حدد الهدف من هذا المصدر قبل البدء: مراجعة، فهم، أو تدريب.',
        'قسّم المصدر إلى جلسات قصيرة وسجل ما لم تفهمه في نهاية كل جلسة.',
        'اربط المصدر بمادة أو خطة أسبوعية حتى لا يتحول إلى ملف مهمل.',
    ]
    by_type = {
        StudentSource.SourceType.TEXT: [
            'اقرأ النص مرة كاملة ثم استخرج الكلمات المفتاحية.',
            'حوّل الفقرات الطويلة إلى أسئلة قصيرة تجيب عنها لاحقًا.',
        ],
        StudentSource.SourceType.PDF: [
            'ابدأ بالفهرس والعناوين قبل قراءة التفاصيل.',
            'ضع علامة على الصفحات التي تحتاج مراجعة ثانية.',
        ],
        StudentSource.SourceType.DOCUMENT: [
            'راجع العناوين والجداول أولًا ثم لخّص كل قسم بسطرين.',
            'استخرج التعاريف والقوانين في قائمة مستقلة.',
        ],
        StudentSource.SourceType.PRESENTATION: [
            'حوّل كل شريحة إلى سؤال واحد أو مهمة مراجعة.',
            'انتبه للرسوم والجداول لأنها غالبًا تلخص الفكرة الرئيسية.',
        ],
        StudentSource.SourceType.IMAGE: [
            'حوّل الصورة إلى ملاحظات قصيرة قبل حفظها.',
            'اكتب ما يظهر في الصورة يدويًا إذا كان نصًا مهمًا.',
        ],
        StudentSource.SourceType.AUDIO: [
            'استمع مرة كاملة دون توقف ثم أعد الاستماع مع تدوين النقاط.',
            'قسّم المحاضرة إلى مقاطع زمنية قصيرة للمراجعة.',
        ],
    }
    return by_type.get(
        source.source_type,
        ['ابدأ بتحديد نوع المعلومات المهمة داخل المصدر.'],
    ) + common


def build_collection_study_advice(collection):
    sources = list(collection.sources.all())
    type_counts = Counter(source.source_type for source in sources)
    advice = [
        'ابدأ بترتيب المصادر حسب الأولوية: المهم للاختبار أولًا ثم المراجع الإضافية.',
        'خصص جلسة مراجعة شاملة للمجلد بعد الانتهاء من المصادر الأساسية.',
    ]

    if collection.subject_id:
        advice.append(f'اربط كل جلسات المجلد بمادة {collection.subject.name} لتبقى الخطة مركزة.')
    else:
        advice.append('اختر مادة للمجلد إذا أردت تحويله لاحقًا إلى خطة أو اختبار مرتبطين بمادة.')

    if type_counts.get(StudentSource.SourceType.PDF):
        advice.append('اقرأ ملفات PDF أولًا عبر العناوين والفهرس ثم حوّل الملاحظات إلى نقاط.')
    if type_counts.get(StudentSource.SourceType.PRESENTATION):
        advice.append('تعامل مع العروض كخريطة للمحاضرة وحوّل كل شريحة إلى سؤال مراجعة.')
    if type_counts.get(StudentSource.SourceType.DOCUMENT):
        advice.append('راجع مستندات Word بعد ملفات العرض لأنها غالبًا تحتوي التفاصيل.')
    if type_counts.get(StudentSource.SourceType.IMAGE):
        advice.append('اكتب الملاحظات المهمة من الصور يدويًا لأن OCR غير مفعّل الآن.')
    if any(source.extracted_text for source in sources):
        advice.append('استخدم فاحص بعد قراءة المصادر النصية الجاهزة لإنشاء أسئلة تدريبية.')
    else:
        advice.append('شغّل معالجة ملفات TXT أولًا إن وجدت للحصول على أسئلة أفضل من فاحص.')

    return advice


@transaction.atomic
def use_source_with_character(user, source, character, action=None):
    capabilities = get_source_character_capabilities(source)
    character_capability = capabilities.get(character)
    if character_capability is None:
        raise ValidationError({'character': 'الشخصية غير مدعومة.'})

    if character == StudentSourceInteraction.Character.KHOLASA:
        return _create_unavailable_interaction(
            user=user,
            source=source,
            character=character,
            action=StudentSourceInteraction.Action.SUMMARIZE,
            message='خلاصة غير متوفرة حاليًا. قريبًا ستساعدك في تلخيص مصادر الدراسة.',
        )
    if character == StudentSourceInteraction.Character.SADA:
        return _create_unavailable_interaction(
            user=user,
            source=source,
            character=character,
            action=StudentSourceInteraction.Action.VOICE_HELP,
            message='صدى غير متوفر حاليًا. قريبًا سيدعم المحاضرات الصوتية.',
        )
    if character == StudentSourceInteraction.Character.RASHEED:
        return _use_source_with_rasheed(user, source)
    if character == StudentSourceInteraction.Character.KHOTA:
        return _use_source_with_khota(user, source)
    if character == StudentSourceInteraction.Character.FAHES:
        return _use_source_with_fahes(user, source)

    raise ValidationError({'character': 'الشخصية غير مدعومة.'})


@transaction.atomic
def use_collection_with_character(user, collection, character, action=None):
    capabilities = get_collection_character_capabilities(collection)
    character_capability = capabilities.get(character)
    if character_capability is None:
        raise ValidationError({'character': 'الشخصية غير مدعومة.'})

    if character == StudentSourceInteraction.Character.KHOLASA:
        return _create_unavailable_interaction(
            user=user,
            collection=collection,
            character=character,
            action=StudentSourceInteraction.Action.SUMMARIZE,
            message='خلاصة غير متوفرة حاليًا. قريبًا ستساعدك في تلخيص المجلد كاملًا.',
        )
    if character == StudentSourceInteraction.Character.SADA:
        return _create_unavailable_interaction(
            user=user,
            collection=collection,
            character=character,
            action=StudentSourceInteraction.Action.VOICE_HELP,
            message='صدى غير متوفر حاليًا. قريبًا سيدعم المحاضرات الصوتية داخل المجلد.',
        )
    if character == StudentSourceInteraction.Character.RASHEED:
        return _use_collection_with_rasheed(user, collection)
    if character == StudentSourceInteraction.Character.KHOTA:
        return _use_collection_with_khota(user, collection)
    if character == StudentSourceInteraction.Character.FAHES:
        return _use_collection_with_fahes(user, collection)

    raise ValidationError({'character': 'الشخصية غير مدعومة.'})


def _create_unavailable_interaction(user, character, action, message, source=None, collection=None):
    interaction = _create_interaction(
        user=user,
        source=source,
        collection=collection,
        character=character,
        action=action,
        status=StudentSourceInteraction.Status.UNAVAILABLE,
        message=message,
    )
    return {
        'success': False,
        'available': False,
        'message': message,
        'interaction': interaction,
    }


def _create_failed_interaction(user, character, action, message, source=None, collection=None):
    interaction = _create_interaction(
        user=user,
        source=source,
        collection=collection,
        character=character,
        action=action,
        status=StudentSourceInteraction.Status.FAILED,
        message=message,
    )
    return {
        'success': False,
        'available': True,
        'message': message,
        'interaction': interaction,
    }


def _create_interaction(
    user,
    character,
    action,
    status,
    message,
    source=None,
    collection=None,
    result_type='',
    result_id=None,
    metadata=None,
):
    return StudentSourceInteraction.objects.create(
        user=user,
        source=source,
        collection=collection,
        character=character,
        action=action,
        status=status,
        result_type=result_type,
        result_id=result_id,
        message=message,
        metadata=metadata or {},
    )


def _use_source_with_rasheed(user, source):
    advice = build_study_advice(source)
    interaction = _create_interaction(
        user=user,
        source=source,
        character=StudentSourceInteraction.Character.RASHEED,
        action=StudentSourceInteraction.Action.STUDY_ADVICE,
        status=StudentSourceInteraction.Status.COMPLETED,
        message='رشيد جهّز لك إرشادات للتعامل مع هذا المصدر.',
        metadata={'advice': advice},
    )
    return {
        'success': True,
        'message': interaction.message,
        'advice': advice,
        'interaction': interaction,
    }


def _use_source_with_khota(user, source):
    if source.subject_id is None:
        return _create_failed_interaction(
            user=user,
            source=source,
            character=StudentSourceInteraction.Character.KHOTA,
            action=StudentSourceInteraction.Action.CREATE_STUDY_PLAN,
            message='اختر مادة للمصدر أولًا حتى تستطيع خُطى إنشاء خطة مذاكرة.',
        )

    plan = _create_study_plan_from_sources(
        user=user,
        title=f'خطة مذاكرة: {source.title}',
        description=f'خطة مبدئية مبنية على المصدر: {source.original_filename}',
        subject=source.subject,
        sources=[source],
    )
    interaction = _create_interaction(
        user=user,
        source=source,
        character=StudentSourceInteraction.Character.KHOTA,
        action=StudentSourceInteraction.Action.CREATE_STUDY_PLAN,
        status=StudentSourceInteraction.Status.COMPLETED,
        result_type='study_plan',
        result_id=plan.id,
        message='أنشأت خُطى خطة مذاكرة مبدئية من مصدرك.',
        metadata={'source_id': source.id, 'study_plan_id': plan.id},
    )
    return {'success': True, 'message': interaction.message, 'interaction': interaction, 'study_plan': plan}


def _use_source_with_fahes(user, source):
    if source.subject_id is None:
        return _create_failed_interaction(
            user=user,
            source=source,
            character=StudentSourceInteraction.Character.FAHES,
            action=StudentSourceInteraction.Action.CREATE_QUIZ,
            message='اختر مادة للمصدر أولًا حتى يستطيع فاحص إنشاء اختبار.',
        )

    quiz, created_questions = _create_quiz_from_sources(
        user=user,
        title=f'اختبار من: {source.title}',
        description=f'اختبار مبدئي مرتبط بالمصدر: {source.original_filename}',
        topic=source.title,
        subject=source.subject,
        sources=[source],
    )
    message = (
        'جهّز فاحص اختبارًا مبدئيًا من مصدرك مع أسئلة تدريبية بسيطة.'
        if created_questions
        else 'جهّز فاحص اختبارًا مبدئيًا مرتبطًا بالمصدر. توليد الأسئلة يحتاج نصًا مستخرجًا أو خدمة AI لاحقًا.'
    )
    interaction = _create_interaction(
        user=user,
        source=source,
        character=StudentSourceInteraction.Character.FAHES,
        action=StudentSourceInteraction.Action.CREATE_QUIZ,
        status=StudentSourceInteraction.Status.COMPLETED,
        result_type='quiz',
        result_id=quiz.id,
        message=message,
        metadata={'source_id': source.id, 'quiz_id': quiz.id, 'questions_count': created_questions},
    )
    return {'success': True, 'message': message, 'interaction': interaction, 'quiz': quiz}


def _use_collection_with_rasheed(user, collection):
    advice = build_collection_study_advice(collection)
    interaction = _create_interaction(
        user=user,
        collection=collection,
        character=StudentSourceInteraction.Character.RASHEED,
        action=StudentSourceInteraction.Action.STUDY_ADVICE,
        status=StudentSourceInteraction.Status.COMPLETED,
        message='رشيد جهّز لك إرشادات لتنظيم هذا المجلد.',
        metadata={'advice': advice, 'collection_id': collection.id},
    )
    return {'success': True, 'message': interaction.message, 'advice': advice, 'interaction': interaction}


def _use_collection_with_khota(user, collection):
    sources = list(collection.sources.select_related('subject').order_by('created_at'))
    if not sources:
        return _create_failed_interaction(
            user=user,
            collection=collection,
            character=StudentSourceInteraction.Character.KHOTA,
            action=StudentSourceInteraction.Action.CREATE_STUDY_PLAN,
            message='أضف مصادر إلى هذا المجلد أولًا.',
        )

    subject = _resolve_collection_subject(collection, sources)
    if subject is None:
        return _create_failed_interaction(
            user=user,
            collection=collection,
            character=StudentSourceInteraction.Character.KHOTA,
            action=StudentSourceInteraction.Action.CREATE_STUDY_PLAN,
            message='اختر مادة للمجلد قبل إنشاء خطة.',
        )

    plan = _create_study_plan_from_sources(
        user=user,
        title=f'خطة مذاكرة: {collection.name}',
        description=f'خطة مبدئية مبنية على مجلد: {collection.name}',
        subject=subject,
        sources=sources,
    )
    interaction = _create_interaction(
        user=user,
        collection=collection,
        character=StudentSourceInteraction.Character.KHOTA,
        action=StudentSourceInteraction.Action.CREATE_STUDY_PLAN,
        status=StudentSourceInteraction.Status.COMPLETED,
        result_type='study_plan',
        result_id=plan.id,
        message='أنشأت خُطى خطة مذاكرة مبدئية من هذا المجلد.',
        metadata={'collection_id': collection.id, 'study_plan_id': plan.id},
    )
    return {'success': True, 'message': interaction.message, 'interaction': interaction, 'study_plan': plan}


def _use_collection_with_fahes(user, collection):
    sources = list(collection.sources.select_related('subject').order_by('created_at'))
    if not sources:
        return _create_failed_interaction(
            user=user,
            collection=collection,
            character=StudentSourceInteraction.Character.FAHES,
            action=StudentSourceInteraction.Action.CREATE_QUIZ,
            message='أضف مصادر إلى هذا المجلد أولًا.',
        )

    subject = _resolve_collection_subject(collection, sources)
    if subject is None:
        return _create_failed_interaction(
            user=user,
            collection=collection,
            character=StudentSourceInteraction.Character.FAHES,
            action=StudentSourceInteraction.Action.CREATE_QUIZ,
            message='اختر مادة للمجلد قبل إنشاء اختبار.',
        )

    quiz, created_questions = _create_quiz_from_sources(
        user=user,
        title=f'اختبار من مجلد: {collection.name}',
        description=f'اختبار مبدئي مرتبط بمجلد: {collection.name}',
        topic=collection.name,
        subject=subject,
        sources=sources,
    )
    message = (
        'جهّز فاحص اختبارًا من المصادر النصية الجاهزة داخل المجلد.'
        if created_questions
        else 'جهّز فاحص اختبارًا مسودة من المجلد. الأسئلة التفصيلية تحتاج نصًا مستخرجًا لاحقًا.'
    )
    interaction = _create_interaction(
        user=user,
        collection=collection,
        character=StudentSourceInteraction.Character.FAHES,
        action=StudentSourceInteraction.Action.CREATE_QUIZ,
        status=StudentSourceInteraction.Status.COMPLETED,
        result_type='quiz',
        result_id=quiz.id,
        message=message,
        metadata={'collection_id': collection.id, 'quiz_id': quiz.id, 'questions_count': created_questions},
    )
    return {'success': True, 'message': message, 'interaction': interaction, 'quiz': quiz}


def _resolve_collection_subject(collection, sources):
    if collection.subject_id:
        return collection.subject
    for source in sources:
        if source.subject_id:
            return source.subject
    return None


def _create_study_plan_from_sources(user, title, description, subject, sources):
    today = timezone.localdate()
    duration_days = max(min(len(sources) + 2, 10), 3)
    plan = StudyPlan.objects.create(
        user=user,
        subject=subject,
        title=title,
        description=description,
        start_date=today,
        end_date=today + timedelta(days=duration_days),
        daily_study_minutes=45,
        goal='تنظيم مذاكرة المصادر وتحويلها إلى خطوات واضحة.',
        difficulty_level=StudyPlan.DifficultyLevel.MEDIUM,
        status=StudyPlan.Status.ACTIVE,
        generation_type=StudyPlan.GenerationType.MANUAL,
    )

    task_payloads = [
        ('تصفح جميع مصادر المجلد وتحديد العناوين الرئيسية', 'استعرض المصادر وسجل العناوين أو الأفكار الأساسية.'),
    ]
    for source in sources[:4]:
        task_payloads.append(
            (f'مراجعة: {source.title}', 'اقرأ المصدر واكتب ملخصًا قصيرًا وأهم الأسئلة.')
        )
    task_payloads.extend(
        [
            ('حل أسئلة تدريبية', 'حوّل المحتوى إلى أسئلة قصيرة للتدريب.'),
            ('مراجعة شاملة للمجلد', 'راجع الملخصات والأجزاء التي احتجت فيها وقتًا أطول.'),
        ]
    )

    for index, (task_title, task_description) in enumerate(task_payloads, start=1):
        StudyTask.objects.create(
            plan=plan,
            title=task_title,
            description=task_description,
            task_date=today + timedelta(days=min(index - 1, duration_days)),
            estimated_minutes=45,
            priority=StudyTask.Priority.MEDIUM,
            status=StudyTask.Status.PENDING,
            order=index,
        )
    update_plan_completion(plan)
    return plan


def _create_quiz_from_sources(user, title, description, topic, subject, sources):
    quiz = Quiz.objects.create(
        user=user,
        subject=subject,
        title=title,
        description=description,
        topic=topic,
        difficulty_level=DifficultyLevelChoices.MEDIUM,
        quiz_type=QuizTypeChoices.PRACTICE,
        generation_type=GenerationTypeChoices.MANUAL,
        status=QuizStatusChoices.DRAFT,
        questions_count=0,
        time_limit_minutes=10,
    )

    created_questions = 0
    for source in sources:
        if source.extracted_text:
            created_questions += _create_basic_questions_from_text(
                quiz,
                source.extracted_text,
                start_order=created_questions + 1,
            )
        if created_questions >= 5:
            break

    quiz.questions_count = created_questions
    quiz.status = QuizStatusChoices.PUBLISHED if created_questions else QuizStatusChoices.DRAFT
    quiz.save(update_fields=['questions_count', 'status', 'updated_at'])
    return quiz, created_questions


def _create_basic_questions_from_text(quiz, text, start_order=1):
    sentences = [
        item.strip()
        for item in text.replace('\r', '\n').split('\n')
        if len(item.strip()) >= 20
    ][: max(0, 6 - start_order)]
    if not sentences:
        return 0

    for offset, sentence in enumerate(sentences):
        order = start_order + offset
        Question.objects.create(
            quiz=quiz,
            text=f'اشرح باختصار الفكرة التالية من المصدر: {sentence[:120]}',
            question_type=QuestionTypeChoices.SHORT_ANSWER,
            difficulty_level=quiz.difficulty_level,
            explanation='راجع النص الأصلي في المصدر ثم قارن إجابتك بالفكرة الرئيسية.',
            order=order,
            points=1,
        )
    return len(sentences)
