import pytest
import mock

from bcbio.distributed.transaction import tx_tmpdir
from bcbio.distributed.transaction import file_transaction
from bcbio.distributed.transaction import _get_base_tmpdir
from bcbio.distributed.transaction import _get_config_tmpdir
from bcbio.distributed.transaction import _get_config_tmpdir_path
from bcbio.distributed.transaction import _dirs_to_remove
from bcbio.distributed.transaction import _flatten_plus_safe


CWD = 'TEST_CWD'
CONFIG = {'a': 1}


class DummyCM(object):
    value = None

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        pass

    def __getattr__(self, attr):
        return self.stuff.__getattribute__(attr)


class DummyTxTmpdir(DummyCM):
    stuff = 'foo'

    def __iadd__(self, other):
        return self.stuff + other


class DummyFlattenPlusSafe(DummyCM):
    value = ('foo', 'bar')

    def __iter__(self):
        for v in self.value:
            yield v


@pytest.yield_fixture
def mock_tx_tmpdir(mocker):
    yield mocker.patch(
        'bcbio.distributed.transaction.tx_tmpdir',
        side_effect=DummyTxTmpdir
    )


@pytest.yield_fixture
def mock_flatten(mocker):
    yield mocker.patch(
        'bcbio.distributed.transaction._flatten_plus_safe',
        side_effect=DummyFlattenPlusSafe
    )


@mock.patch('bcbio.distributed.transaction.shutil')
@mock.patch('bcbio.distributed.transaction.tempfile')
@mock.patch('bcbio.distributed.transaction.utils.safe_makedir')
@mock.patch('bcbio.distributed.transaction.os.path.exists')
@mock.patch('bcbio.distributed.transaction.os.getcwd', return_value=CWD)
def test_tx_tmpdir_make_tmp_dir(
        mock_getcwd, mock_exists,  mock_makedirs, mock_tempfile, mock_shutil):
    with tx_tmpdir():
        pass
    expected_basedir = "%s/tx" % CWD
    mock_tempfile.mkdtemp.assert_called_once_with(
        dir=expected_basedir)
    mock_makedirs.assert_called_once_with(expected_basedir)


@mock.patch('bcbio.distributed.transaction.shutil')
@mock.patch('bcbio.distributed.transaction.tempfile')
@mock.patch('bcbio.distributed.transaction.utils.safe_makedir')
@mock.patch('bcbio.distributed.transaction.os.path.exists')
@mock.patch('bcbio.distributed.transaction.os.getcwd', return_value=CWD)
def test_tx_tmpdir_yields_tmp_dir(
        mock_getcwd, mock_exists,  mock_makedirs, mock_tempfile, mock_shutil):
    expected = mock_tempfile.mkdtemp.return_value
    with tx_tmpdir() as tmp_dir:
        assert tmp_dir == expected


@mock.patch('bcbio.distributed.transaction.os.path.exists')
@mock.patch('bcbio.distributed.transaction.shutil')
@mock.patch('bcbio.distributed.transaction.tempfile')
@mock.patch('bcbio.distributed.transaction.utils.safe_makedir')
@mock.patch('bcbio.distributed.transaction._get_base_tmpdir')
@mock.patch('bcbio.distributed.transaction._get_config_tmpdir')
@mock.patch('bcbio.distributed.transaction._get_config_tmpdir_path')
@mock.patch('bcbio.distributed.transaction.os.getcwd')
def test_tx_tmpdir_yields_creares_dirs(
        mock_getcwd,
        mock_get_config_tmpdir_path,
        mock_get_config_tmpdir,
        mock_get_base_tmpdir,
        mock_makedirs,
        mock_tempfile,
        mock_shutil,
        mock_exists):
    mock_getcwd.return_value = CWD
    data, base_dir = mock.Mock(), mock.Mock()
    with tx_tmpdir(data, base_dir):
        pass
    mock_get_config_tmpdir.assert_called_once_with(data)
    mock_get_config_tmpdir_path.assert_called_once_with(
        mock_get_config_tmpdir.return_value, CWD)
    mock_get_base_tmpdir.assert_called_once_with(
        base_dir, mock_get_config_tmpdir_path.return_value, CWD)
    mock_makedirs.assert_called_once_with(mock_get_base_tmpdir.return_value)
    mock_tempfile.mkdtemp.assert_called_once_with(
        dir=mock_get_base_tmpdir.return_value)


@pytest.mark.parametrize(
    ('base_dir', 'config_tmp', 'expected'),
    [
        (None, None, CWD + '/tx'),
        ('TEST_BASE_DIR', None, 'TEST_BASE_DIR/tx'),
        (None, 'TEST_CONFIG_TMP', 'TEST_CONFIG_TMP/bcbiotx/TESTID'),
        ('TEST_BASE_DIR', 'TEST_CONFIG_TMP', 'TEST_CONFIG_TMP/bcbiotx/TESTID')
    ]
)
def test_get_base_tmpdir(
        mocker, base_dir, config_tmp, expected):
    mocker.patch(
        'bcbio.distributed.transaction.uuid.uuid4', return_value='TESTID')

    result = _get_base_tmpdir(base_dir, config_tmp, CWD)
    assert result == expected


def test_get_config_tmpdir__from_config():
    config = {
        'config': {
            'resources': {
                'tmp': {'dir': 'TEST_TMP_DIR'}
            }
        }
    }
    expected = 'TEST_TMP_DIR'
    result = _get_config_tmpdir(config)
    assert result == expected


def test_get_config_tmpdir__from_resources():
    config = {
        'resources': {
            'tmp': {'dir': 'TEST_TMP_DIR'}
        }
    }
    expected = 'TEST_TMP_DIR'
    result = _get_config_tmpdir(config)
    assert result == expected


def test_get_config_tmpdir__no_data():
    result = _get_config_tmpdir(None)
    assert result is None


def test_get_config_tmpdir_path():
    result = _get_config_tmpdir_path(None, 'whatever')
    assert result is None


@mock.patch('bcbio.distributed.transaction.os.path')
def test_get_config_tmpdir_path__flow(mock_path):
    TMP = 'TEST_CONFIG_TMP'

    mock_path.expandvars.return_value = 'EXPANDED'
    mock_path.join.return_value = 'JOINED'
    mock_path.normpath.return_value = 'NORMALIZED'

    result = _get_config_tmpdir_path(TMP, CWD)

    mock_path.expandvars.assert_called_once_with(TMP)
    mock_path.join.assert_called_once_with(CWD, 'EXPANDED')
    mock_path.normpath.assert_called_once_with('JOINED')

    assert result == 'NORMALIZED'


@mock.patch('bcbio.distributed.transaction.shutil')
@mock.patch('bcbio.distributed.transaction.tempfile')
@mock.patch('bcbio.distributed.transaction.utils.safe_makedir')
@mock.patch('bcbio.distributed.transaction.os.path.exists')
@mock.patch('bcbio.distributed.transaction.os.getcwd', return_value=CWD)
@mock.patch('bcbio.distributed.transaction._dirs_to_remove')
def test_tx_tmpdir_rmtree_not_called_if_remove_is_false(
        mock_dirs_to_remove, mock_getcwd, mock_exists,
        mock_makedirs, mock_tempfile, mock_shutil):
    mock_dirs_to_remove.return_value = ['foo']
    with tx_tmpdir(remove=False):
        pass
    assert not mock_shutil.rmtree.called


@mock.patch('bcbio.distributed.transaction.shutil')
@mock.patch('bcbio.distributed.transaction.tempfile')
@mock.patch('bcbio.distributed.transaction.utils.safe_makedir')
@mock.patch('bcbio.distributed.transaction.os.path.exists')
@mock.patch('bcbio.distributed.transaction.os.getcwd', return_value=CWD)
@mock.patch('bcbio.distributed.transaction._dirs_to_remove')
def test_tx_tmpdir_rmtree_called_if_remove_is_True(
        mock_dirs_to_remove, mock_getcwd, mock_exists,
        mock_makedirs, mock_tempfile, mock_shutil):
    mock_dirs_to_remove.return_value = ['foo']
    with tx_tmpdir(remove=True):
        pass
    mock_shutil.rmtree.assert_called_once_with('foo', ignore_errors=True)


@pytest.mark.parametrize(
    ('tmp_dir', 'tmp_dir_base', 'config_tmpdir', 'expected'),
    [
        ('foo', 'bar', 'baz', ['foo', 'bar']),
        ('foo', 'bar', None, ['foo']),
        (None, None, 'baz', []),
        ('foo', None, 'baz', ['foo']),
        (None, 'bar', 'baz', ['bar']),
    ]
)
def test_get_dirs_to_remove(tmp_dir, tmp_dir_base, config_tmpdir, expected):
    result = _dirs_to_remove(tmp_dir, tmp_dir_base, config_tmpdir)
    assert list(result) == expected


@pytest.mark.parametrize(('args', 'exp_tx_args'), [
    (('/path/to/somefile',), (None, '/path/to')),
    ((CONFIG, '/path/to/somefile'), (CONFIG, '/path/to')),
    ((CONFIG, ['/path/to/somefile']), (CONFIG, '/path/to')),
    ((CONFIG, '/path/to/somefile', '/otherpath/to/file'), (CONFIG, '/path/to'))
])
def test_flatten_plus_safe_calls_tx_tmpdir(args, exp_tx_args, mock_tx_tmpdir):
    with _flatten_plus_safe(args) as (result_tx, result_safe):
        pass
    mock_tx_tmpdir.assert_called_once_with(*exp_tx_args)


@pytest.mark.parametrize(('args', 'expected_tx'), [
    (('/path/to/somefile',), ['foo/somefile']),
    ((CONFIG, '/path/to/somefile'), ['foo/somefile']),
    ((CONFIG, ['/path/to/somefile']), ['foo/somefile']),
    (
        (CONFIG, '/path/to/somefile', '/otherpath/to/otherfile'),
        ['foo/somefile', 'foo/otherfile'],
    )]
)
def test_flatten_plus_safe_creates_tx_file_in_tmp_dir(
        args, expected_tx, mock_tx_tmpdir):
    with _flatten_plus_safe(args) as (result_tx, _):
        assert result_tx == expected_tx


@pytest.mark.parametrize(('args', 'expected_safe'), [
    (('/path/to/somefile',), ['/path/to/somefile']),
    ((CONFIG, '/path/to/somefile'), ['/path/to/somefile']),
    ((CONFIG, ['/path/to/somefile']), ['/path/to/somefile']),
    (
        (CONFIG, '/path/to/somefile', '/otherpath/to/otherfile'),
        ['/path/to/somefile', '/otherpath/to/otherfile'],
    )]
)
def test_flatten_plus_safe_returns_original_files(
        args, expected_safe, mock_tx_tmpdir):
    with _flatten_plus_safe(args) as (_, result_safe):
        assert result_safe == expected_safe


def test_flatten_plus_safe_filters_args(mock_tx_tmpdir):
    args = ({}, ['/path/to/somefile'])
    with _flatten_plus_safe(args) as (_, _):
        pass
    mock_tx_tmpdir.assert_called_once_with(None, '/path/to')


def test_flatten_plus_raises_if_empty_fpaths(mock_tx_tmpdir):
    args = (CONFIG, [])
    with pytest.raises(IndexError):
        with _flatten_plus_safe(args) as (_, _):
            pass


@mock.patch('bcbio.distributed.transaction.os.remove')
@mock.patch('bcbio.distributed.transaction.shutil')
@mock.patch('bcbio.distributed.transaction.os.path.exists')
@mock.patch('bcbio.distributed.transaction.os.getcwd')
def test_file_transaction(
        mock_getcwd, mock_path, mock_shutil, mock_remove, mock_flatten):
    with file_transaction(CONFIG, '/some/path'):
        pass
    pass
