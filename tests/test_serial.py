
import labbench as lb


def test_serial_device():
    TEST_STRING = b'hello'
    with lb.SerialDevice('loop://') as dev:
        dev.backend.write(TEST_STRING)
        assert dev.backend.read_all() == TEST_STRING, 'loopback test'

def test_serial_logging_device():
    STRINGS = b'1\n', b'2\n'
    with lb.SerialLoggingDevice('loop://', stop_timeout=0.1) as dev:
        dev.start()
        for s in STRINGS:
            dev.backend.write(s)
        dev.stop()
        assert b''.join(STRINGS) == dev.fetch(), 'loopback test'
