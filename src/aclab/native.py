"""Explicit native backend. Serialized protocol, bounded waits, no fallback."""
import asyncio
import hashlib
import os
import tempfile
import time
from pathlib import Path
import json
from .types import LabError, canonical

class NativeBlaze:
    def __init__(self, registry, binary=None):
        self.registry=registry
        self.binary=Path(binary or os.environ.get('ACLAB_BLAZE_WORKER',''))
        if not self.binary.is_file():
            raise LabError('VALIDATOR_UNAVAILABLE','Set blaze_worker_path to a compiled native worker; no fallback')
        self.identity={'engine':'blaze','binary_sha256':hashlib.sha256(self.binary.read_bytes()).hexdigest()}
        self.temp=tempfile.TemporaryDirectory(prefix='aclab-blaze-')
        for name,c in registry.contracts.items():
            for direction in ('input','output'):
                Path(self.temp.name,f'{name}-{direction}.json').write_text(canonical(c[f'{direction}_schema']))
        self.lock=asyncio.Lock();self.process=None;self.calls=[];self.ready=None

    async def _stop(self):
        if self.process and self.process.returncode is None:
            self.process.kill()
            await self.process.wait()
        self.process=None

    async def validate(self,name,direction,instance):
        self.registry.get(name)
        try:payload=canonical(instance)
        except (ValueError,TypeError):return ['Instance must be finite JSON']
        async with self.lock:
            try:
                async with asyncio.timeout(5):
                    if self.process is None:
                        self.process=await asyncio.create_subprocess_exec(str(self.binary.resolve()),self.temp.name,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
                        self.ready=json.loads(await self.process.stdout.readline())
                        if not self.ready.get('ready'):raise ValueError('Native startup failed')
                    start=time.perf_counter_ns()
                    self.process.stdin.write(f'{name}-{direction}\t1\t{payload}\n'.encode())
                    await self.process.stdin.drain()
                    result=json.loads(await self.process.stdout.readline())
                    if type(result.get('valid')) is not bool or result.get('iterations')!=1 or result.get('checksum')!=int(result['valid']):
                        raise ValueError('Invalid native reply')
                    self.calls.append({'name':name,'direction':direction,**result,'ipc_wall_ns':time.perf_counter_ns()-start})
                    return [] if result['valid'] else ['Native Blaze rejected instance']
            except asyncio.CancelledError:
                await self._stop();raise
            except (TimeoutError,ValueError,TypeError,OSError,KeyError) as exc:
                await self._stop()
                raise LabError('VALIDATOR_UNAVAILABLE','Native Blaze failed; no fallback') from exc

    async def close(self):
        async with self.lock:
            await self._stop();self.temp.cleanup()
