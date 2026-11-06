import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import pytest
from botshelf.codex_provider import CodexClient
from botshelf.shelf_models import RewritePlan

PLAN=dict(ordered_block_ids=['a'],decisive_block_id=None,merchant_questions=[])


def test_codex_schema_isolation_and_usage():
    def runner(command, **kwargs):
        assert '--ignore-user-config' in command and '--ephemeral' in command
        assert command[command.index('--sandbox')+1]=='read-only'
        assert command[command.index('--model')+1]=='test-model'
        assert 'shell_tool' in command and 'plugins' in command
        assert kwargs['timeout']==180 and 'shell' not in kwargs
        assert 'untrusted text' in kwargs['input']
        schema=json.loads(Path(command[command.index('--output-schema')+1]).read_text())
        assert schema['additionalProperties'] is False
        Path(command[command.index('--output-last-message')+1]).write_text(json.dumps(PLAN))
        return SimpleNamespace(returncode=0,stdout=json.dumps({'type':'turn.completed','usage':{'input_tokens':12,'output_tokens':7}}))
    result,ins,outs=CodexClient(binary='python3',runner=runner).structured(RewritePlan,'rules',{'text':'untrusted text'},'test-model')
    assert result.ordered_block_ids==['a'] and (ins,outs)==(12,7)


@pytest.mark.parametrize('fault',['malformed','tool','failed','incomplete','timeout'])
def test_codex_fails_closed(fault):
    def runner(command,**kwargs):
        if fault=='timeout': raise subprocess.TimeoutExpired(command,180)
        Path(command[command.index('--output-last-message')+1]).write_text('invalid' if fault=='malformed' else json.dumps(PLAN))
        event={'type':'turn.completed'}
        if fault=='tool': event={'type':'item.completed','item':{'type':'command_execution'}}
        if fault=='failed': event={'type':'turn.failed'}
        if fault=='incomplete': event={'type':'thread.started'}
        return SimpleNamespace(returncode=0,stdout=json.dumps(event))
    with pytest.raises((ValueError,RuntimeError,subprocess.TimeoutExpired)):
        CodexClient(binary='python3',runner=runner).structured(RewritePlan,'rules',{},'test-model')
