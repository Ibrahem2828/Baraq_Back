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

from .capabilities import get_source_character_capabilities
from .models import StudentSource, StudentSourceInteraction


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
            message = 'تم حفظ الملف الصوتي. التفريغ الصوتي عبر صدى غير متوفر حاليًا.'
        else:
            source.status = StudentSource.Status.UPLOADED
            message = 'تم حفظ المصدر. المعالجة المتقدمة لهذا النوع غير متوفرة حاليًا.'

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
        return {'success': False, 'message': 'فشلت معالجة المصدر.', 'error': str(exc)}


def _read_text_file(source):
    with source.file.open('rb') as file_obj:
        content = file_obj.read(TXT_READ_LIMIT_BYTES + 1)

    if len(content) > TXT_READ_LIMIT_BYTES:
        raise ValidationError('Text file is too large to process synchronously.')

    for encoding in ('utf-8-sig', 'utf-8', 'cp1256', 'latin-1'):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise ValidationError('Unable to decode text file.')


def build_study_advice(source):
    common = [
        'حدد الهدف من هذا المصدر قبل البدء: مراجعة، فهم، أو تدريب.',
        'قسّم المصدر إلى جلسات قصيرة وسجّل ما لم تفهمه في نهاية كل جلسة.',
        'اربط المصدر بمادة واحدة وخطة أسبوعية حتى لا يتحول إلى ملف مهمل.',
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
    return by_type.get(source.source_type, ['ابدأ بتحديد نوع المعلومات المهمة داخل المصدر.']) + common


@transaction.atomic
def use_source_with_character(user, source, character, action=None):
    capabilities = get_source_character_capabilities(source)
    character_capability = capabilities.get(character)
    if character_capability is None:
        raise ValidationError({'character': 'Unsupported character.'})

    if character == StudentSourceInteraction.Character.KHOLASA:
        return _create_unavailable_interaction(
            user,
            source,
            character,
            StudentSourceInteraction.Action.SUMMARIZE,
            'خلاصة غير متوفرة حاليًا. قريبًا ستساعدك في تلخيص مصادر الدراسة.',
        )
    if character == StudentSourceInteraction.Character.SADA:
        return _create_unavailable_interaction(
            user,
            source,
            character,
            StudentSourceInteraction.Action.VOICE_HELP,
            'صدى غير متوفر حاليًا. قريبًا سيساعدك في المحاضرات الصوتية.',
        )
    if character == StudentSourceInteraction.Character.RASHEED:
        return _use_with_rasheed(user, source)
    if character == StudentSourceInteraction.Character.KHOTA:
        return _use_with_khota(user, source)
    if character == StudentSourceInteraction.Character.FAHES:
        return _use_with_fahes(user, source)

    raise ValidationError({'character': 'Unsupported character.'})


def _create_unavailable_interaction(user, source, character, action, message):
    interaction = StudentSourceInteraction.objects.create(
        user=user,
        source=source,
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


def _use_with_rasheed(user, source):
    advice = build_study_advice(source)
    interaction = StudentSourceInteraction.objects.create(
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


def _use_with_khota(user, source):
    if source.subject_id is None:
        return _create_failed_interaction(
            user,
            source,
            StudentSourceInteraction.Character.KHOTA,
            StudentSourceInteraction.Action.CREATE_STUDY_PLAN,
            'اختر مادة للمصدر أولًا حتى تستطيع خُطى إنشاء خطة مذاكرة.',
        )

    today = timezone.localdate()
    plan = StudyPlan.objects.create(
        user=user,
        subject=source.subject,
        title=f'خطة مذاكرة: {source.title}',
        description=f'خطة مبدئية مبنية على المصدر: {source.original_filename}',
        start_date=today,
        end_date=today + timedelta(days=3),
        daily_study_minutes=45,
        goal='تنظيم مذاكرة المصدر وتحويله إلى خطوات واضحة.',
        difficulty_level=StudyPlan.DifficultyLevel.MEDIUM,
        status=StudyPlan.Status.ACTIVE,
        generation_type=StudyPlan.GenerationType.MANUAL,
    )

    task_payloads = [
        ('قراءة المصدر وتحديد العناوين الرئيسية', 'استعرض المصدر وسجل العناوين أو الأفكار الأساسية.', 1),
        ('تلخيص النقاط المهمة', 'اكتب ملخصًا قصيرًا لأهم القوانين أو المفاهيم.', 2),
        ('حل أسئلة تدريبية من المصدر', 'حوّل المحتوى إلى أسئلة قصيرة للتدريب.', 3),
        ('مراجعة الأخطاء', 'راجع الإجابات والأجزاء التي احتجت فيها وقتًا أطول.', 4),
    ]
    for index, (title, description, order) in enumerate(task_payloads):
        StudyTask.objects.create(
            plan=plan,
            title=title,
            description=description,
            task_date=today + timedelta(days=min(index, 3)),
            estimated_minutes=45,
            priority=StudyTask.Priority.MEDIUM,
            status=StudyTask.Status.PENDING,
            order=order,
        )
    update_plan_completion(plan)

    interaction = StudentSourceInteraction.objects.create(
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
    return {
        'success': True,
        'message': interaction.message,
        'interaction': interaction,
        'study_plan': plan,
    }


def _use_with_fahes(user, source):
    if source.subject_id is None:
        return _create_failed_interaction(
            user,
            source,
            StudentSourceInteraction.Character.FAHES,
            StudentSourceInteraction.Action.CREATE_QUIZ,
            'اختر مادة للمصدر أولًا حتى يستطيع فاحص إنشاء اختبار.',
        )

    quiz = Quiz.objects.create(
        user=user,
        subject=source.subject,
        title=f'اختبار من: {source.title}',
        description=f'اختبار مبدئي مرتبط بالمصدر: {source.original_filename}',
        topic=source.title,
        difficulty_level=DifficultyLevelChoices.MEDIUM,
        quiz_type=QuizTypeChoices.PRACTICE,
        generation_type=GenerationTypeChoices.MANUAL,
        status=QuizStatusChoices.DRAFT,
        questions_count=0,
        time_limit_minutes=10,
    )

    created_questions = 0
    if source.extracted_text:
        created_questions = _create_basic_questions_from_text(quiz, source.extracted_text)
        quiz.questions_count = created_questions
        quiz.status = QuizStatusChoices.PUBLISHED if created_questions else QuizStatusChoices.DRAFT
        quiz.save(update_fields=['questions_count', 'status', 'updated_at'])

    message = (
        'جهّز فاحص اختبارًا مبدئيًا من مصدرك مع أسئلة تدريبية بسيطة.'
        if created_questions
        else 'جهّز فاحص اختبارًا مبدئيًا مرتبطًا بالمصدر. توليد الأسئلة يحتاج نصًا مستخرجًا أو خدمة AI لاحقًا.'
    )
    interaction = StudentSourceInteraction.objects.create(
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
    return {
        'success': True,
        'message': message,
        'interaction': interaction,
        'quiz': quiz,
    }


def _create_basic_questions_from_text(quiz, text):
    sentences = [
        item.strip()
        for item in text.replace('\r', '\n').split('\n')
        if len(item.strip()) >= 20
    ][:3]
    if not sentences:
        return 0

    for index, sentence in enumerate(sentences, start=1):
        Question.objects.create(
            quiz=quiz,
            text=f'اشرح باختصار الفكرة التالية من المصدر: {sentence[:120]}',
            question_type=QuestionTypeChoices.SHORT_ANSWER,
            difficulty_level=quiz.difficulty_level,
            explanation='راجع النص الأصلي في المصدر ثم قارن إجابتك بالفكرة الرئيسية.',
            order=index,
            points=1,
        )
    return len(sentences)


def _create_failed_interaction(user, source, character, action, message):
    interaction = StudentSourceInteraction.objects.create(
        user=user,
        source=source,
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
