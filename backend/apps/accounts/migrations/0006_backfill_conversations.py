from django.db import migrations


def forwards(apps, schema_editor):
    Conversation = apps.get_model("accounts", "ChatConversation")
    Message = apps.get_model("accounts", "AccountChatMessage")
    Account = apps.get_model("accounts", "TemporaryAccount")
    account_ids = Message.objects.filter(conversation__isnull=True, account__isnull=False).values_list("account_id", flat=True).distinct()
    for account in Account.objects.filter(id__in=list(account_ids)).select_related("job"):
        convo, _ = Conversation.objects.get_or_create(account=account, defaults={"user_id": account.job.user_id})
        Message.objects.filter(account=account, conversation__isnull=True).update(conversation=convo)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_chat_conversations")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
