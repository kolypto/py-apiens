from apiens.tools.web.shortid import shortid2uuid, uuid2shortid, UUID


def test_shortid():
    """ Test: shortid """
    id = UUID(bytes=b'\xDE\xAD\xBE\xEF'*4)

    assert uuid2shortid(id) == '3q2-796tvu_erb7v3q2-7w'
    assert shortid2uuid('3q2-796tvu_erb7v3q2-7w') == id
