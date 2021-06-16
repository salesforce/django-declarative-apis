Aggregates
==========

DDA uses aggregates to perform memoization to avoid repeated calculations, querying, or any task that can be performed once and the result cached.
Aggregates retrieve or create a related object based on one or more field that is in use in the EndpointDefinition. An aggregate is calculated only once and then the data is cached for future retrieval.

**Aggregates are used as decorators on functions.**

.. code-block:: python

    from django-declarative-apis.machinery import aggregate

    class SampleClass:
        # code

        @aggregate
        def sample_function():
            # code

**Parameters**

:code:`required`
    **Optional |** Defines whether the aggregate is required or not.

    **Default Value |** :code:`False`

:code:`depends_on`
    **Optional |** Reference to another aggregate that should be run before this aggregate.

    **Default Value |** :code:`None`

    **Example:**
    We want to query a user only once and cache that information for future use.

    .. code-block:: python

        from django-declarative-apis.machinery import aggregate

        class SampleClass:
            user_id = url_field()

            @aggregate(required=True)
            def get_user(self):
                try:
                    user = models.User.objects.get(id=self.user_id)
                except:
                    raise Exception("User with matching id not found")
                return user

