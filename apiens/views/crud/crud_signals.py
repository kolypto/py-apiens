""" CRUD signals """

import blinker


# An instance has been prepared for saving
# Sent: before flush, so the instance doesn't yet have its database ids. For instance, the primary key is not known yet
# Sender: CRUD Class
on_create_prepared = blinker.signal('on_create_prepared')  # (sender: Type[CrudBase], *, crud: CrudBase, new: object)
on_update_prepared = blinker.signal('on_update_prepared')  # (sender: Type[CrudBase], *, new: CrudBase, prev: object)
on_delete_prepared = blinker.signal('on_delete_prepared')  # (sender: Type[CrudBase], *, prev: object)
on_save_prepared = blinker.signal('on_save_prepared')  # (sender: Type[CrudBase], *, new: Optional[object], prev: Optional[object], action='create')

# An instance is being saved.
# Sent: after flush, so the instance has already gotten its database ids
# Sender: CRUD Class
on_create = blinker.signal('on_create')  # (sender: Type[CrudBase], *, new: object)
on_update = blinker.signal('on_update')  # (sender: Type[CrudBase], *, new: object, prev: object)
on_delete = blinker.signal('on_delete')  # (sender: Type[CrudBase], *, prev: object) NOTE: it's already deleted; be careful, you can't load anything
on_save = blinker.signal('on_save')  # (sender: Type[CrudBase], *, new: Optional[object], prev: Optional[object], action='create')


# Commit
# Sender: CRUD Class
on_commit_before = blinker.signal('on_commit_before')  # (sender: Type[CrudBase], *, crud: CrudBase)
on_commit_after = blinker.signal('on_commit_after')  # (sender: Type[CrudBase], *, crud: CrudBase)


# Rollback
# Sender: CRUD Class
on_rollback_before = blinker.signal('on_rollback_before')  # (sender: Type[CrudBase], *, crud: CrudBase)
on_rollback_after = blinker.signal('on_rollback_after')  # (sender: Type[CrudBase], *, crud: CrudBase)
