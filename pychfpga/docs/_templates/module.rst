{{ fullname }}
{{ underline }}


.. automodule:: {{ fullname }}

Simplified
----------

   {% block classes %}
   {% if classes %}

Classes
+++++++

   .. autosummary::
      :nosignatures:

   {% for item in classes %}
      {{ item }}
   {%- endfor %}
   {% endif %}
   {% endblock %}

  {% block functions %}
   {% if functions %}

Functions
+++++++++

   .. autosummary::
      :nosignatures:
   {% for item in functions %}
      {{ fullname }}.{{ item }}
   {%- endfor %}
   {% endif %}
   {% endblock %}

   {% block exceptions %}
   {% if exceptions %}

Exceptions
++++++++++

   .. autosummary::
   {% for item in exceptions %}
      {{ item }}
   {%- endfor %}
   {% endif %}
   {% endblock %}

Verbose
-------

   {% block classes_verbose %}
   {% if classes %}

Classes
+++++++

   {% for item in classes %}

   .. autoclass:: {{ item }}
		  :members:
	
   {%- endfor %}

   {% endif %}
   {% endblock %}


   {% block functions_verbose %}
   {% if functions %}


Functions
+++++++++

   {% for item in functions %}
	.. autofunction:: {{ fullname }}.{{ item }}
   {%- endfor %}
   {% endif %}
   {% endblock %}
   

   {% block exceptions_verbose %}
   {% if exceptions %}

Exceptions
++++++++++

   {% for item in exceptions %}
	.. autoexception:: {{ fullname }}.{{ item }}
   {%- endfor %}
   {% endif %}
   {% endblock %}
