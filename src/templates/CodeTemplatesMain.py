#
#     Copyright 2010, Kay Hayen, mailto:kayhayen@gmx.de
#
#     Part of "Nuitka", an attempt of building an optimizing Python compiler
#     that is compatible and integrates with CPython, but also works on its
#     own.
#
#     If you submit Kay Hayen patches to this software in either form, you
#     automatically grant him a copyright assignment to the code, or in the
#     alternative a BSD license to the code, should your jurisdiction prevent
#     this. Obviously it won't affect code that comes to him indirectly or
#     code you don't submit to him.
#
#     This is to reserve my ability to re-license the code at any time, e.g.
#     the PSF. With this version of Nuitka, using it for Closed Source will
#     not be allowed.
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, version 3 of the License.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#     Please leave the whole of this copyright notice intact.
#


module_inittab_entry = """\
(char *)"%(module_name)s", init%(module_identifier)s,"""

main_program = """\
// Our own inittab for lookup of "frozen" modules, i.e. the ones included in this binary.
static struct _inittab _module_inittab[] =
{
%(module_inittab)s
    NULL, NULL
};

bool FIND_EMBEDDED_MODULE( char const *name )
{
    struct _inittab *current = _module_inittab;

    while ( current->name != NULL )
    {
       if ( strcmp( name, current->name ) == 0 )
       {
           current->initfunc();

           if ( PyErr_Occurred() )
           {
              throw _PythonException();
           }

           return true;
       }

       current++;
    }

    return false;
}

// The main program for C++. It needs to prepare the interpreter and then calls the
// initialization code of the __main__ module.

int main( int argc, char *argv[] )
{
    // Register the initialization functions for modules included in the binary if any
    int res = PyImport_ExtendInittab( _module_inittab );
    assert( res != -1 );

    Py_Initialize();
    PySys_SetArgv( argc, argv );

    // Initialize the constant values used.
    _initConstants();

    // Initialize the compiled types of Nuitka.
    PyType_Ready( &Nuitka_Generator_Type );
    PyType_Ready( &Nuitka_Function_Type );
    PyType_Ready( &Nuitka_Genexpr_Type );

    init__main__();

    if ( PyErr_Occurred() )
    {
        PyErr_Print();
    }
}
"""

package_header_template = """\
#include "nuitka/prelude.hpp"

extern PyObject *_package_%(package_identifier)s;

extern void init%(package_identifier)s(void);
"""

package_body_template = """\
#include "nuitka/prelude.hpp"

// The _package_%(package_identifier)s is a Python object pointer of module type.

PyObject *_package_%(package_identifier)s = NULL;

void init%(package_identifier)s(void)
{
    if ( _package_%(package_identifier)s == NULL )
    {
        _package_%(package_identifier)s = Py_InitModule4(
            "%(package_name)s",      // Module Name
            NULL,                    // No methods
            NULL,                    // No __doc__ is set
            NULL,                    // No self for packages, we don't use it.
            PYTHON_API_VERSION
        );

        assert( _package_%(package_identifier)s );
    }
}

"""

module_header_template = """\

NUITKA_MODULE_INIT_FUNCTION init%(module_identifier)s(void);
extern PyObject *_module_%(module_identifier)s;

"""

module_body_template = """\
#include "nuitka/prelude.hpp"

// The _module_%(module_identifier)s is a Python object pointer of module type.

// Note: For full compatability with CPython, every module variable access needs to go
// through it except for cases where the module cannot possibly have changed in the mean
// time.

PyObject *_module_%(module_identifier)s;

// The module level variables.
%(module_globals)s

// The module function declarations.
%(module_functions_decl)s

// The module function definitions.
%(module_functions_code)s

// The exported interface to CPython. On import of the module, this function gets
// called. It has have that exact function name.

NUITKA_MODULE_INIT_FUNCTION init%(module_identifier)s(void)
{
#ifdef _NUITKA_MODULE
    // In case of a stand alone extension module, need to call initialization the init here
    // because that's how we are going to get called here.

    // Initialize the constant values used.
    _initConstants();

    // Initialize the compiled types of Nuitka.
    PyType_Ready( &Nuitka_Generator_Type );
    PyType_Ready( &Nuitka_Function_Type );
    PyType_Ready( &Nuitka_Genexpr_Type );
#endif

    // puts( "in init%(module_identifier)s" );

    // Create the module object first. There are no methods initially, all are added
    // dynamically in actual code only.  Also no __doc__ is initially set, as it could not
    // contain 0 this way, added early in actual code.  No self for modules, we have no
    // use for it.
    _module_%(module_identifier)s = Py_InitModule4(
        "%(module_name)s",       // Module Name
        NULL,                    // No methods initially, all are added dynamically in actual code only.
        NULL,                    // No __doc__ is initially set, as it could not contain 0 this way, added early in actual code.
        NULL,                    // No self for modules, we don't use it.
        PYTHON_API_VERSION
    );

    assert( _module_%(module_identifier)s );

    // Initialize the standard module attributes.
%(module_inits)s

    // Module code
    bool traceback = false;

    try
    {
%(module_code)s
    }
    catch ( _PythonException &_exception )
    {
        _exception.toPython();

        if ( traceback == false )
        {
            ADD_TRACEBACK( _module_%(module_identifier)s, %(file_identifier)s, _python_str_angle_module, _exception.getLine() );
        }
    }
}
"""

module_plain_init_template = """\
    _mvar_%(module_identifier)s___doc__.assign0( %(doc_identifier)s );
    _mvar_%(module_identifier)s___file__.assign0( %(file_identifier)s );"""

module_package_init_template = """\
    _mvar_%(module_identifier)s___doc__.assign0( %(doc_identifier)s );
    _mvar_%(module_identifier)s___file__.assign0( %(file_identifier)s );
    _mvar_%(module_identifier)s___package__.assign0( %(package_name_identifier)s );

    init%(package_identifier)s();

    SET_ATTRIBUTE( _package_%(package_identifier)s, %(module_name)s, _module_%(module_identifier)s );"""

constant_reading = """
#include "nuitka/prelude.hpp"

// The current line of code execution.
int _current_line;

// We unstream some constant objects using the "cPickle" module function "loads"
static PyObject *_module_cPickle = NULL;
static PyObject *_module_cPickle_function_loads = NULL;

// Sentinel PyObject to be used for all our call iterator endings. It will become
// a PyCObject pointing to NULL. TODO: Hopefully that is unique enough.
PyObject *_sentinel_value = NULL;

%(const_declarations)s

static PyObject *_unstreamConstant( char const *buffer, int size )
{
    PyObject *temp = PyString_FromStringAndSize( buffer, size );

    PyObject *result = PyObject_CallFunctionObjArgs( _module_cPickle_function_loads, temp, NULL );
    assert( result );

    Py_DECREF( temp );

    return result;
}

PyModuleObject *_module_builtin = NULL;

static int _initConstants()
{
    if ( _sentinel_value == NULL )
    {
        _sentinel_value = PyCObject_FromVoidPtr( NULL, NULL );
        assert( _sentinel_value );

        _module_builtin = (PyModuleObject *)PyImport_ImportModule( "__builtin__" );
        assert( _module_builtin );

#if PY_MAJOR_VERSION < 3
        _module_cPickle = PyImport_ImportModule( "cPickle" );
#else
        _module_cPickle = PyImport_ImportModule( "pickle" );
#endif
        assert( _module_cPickle );

        _module_cPickle_function_loads = PyObject_GetAttrString( _module_cPickle, "loads" );
        assert( _module_cPickle_function_loads );

        %(const_init)s
    }
}
"""

module_header = """
// Generated code for Python source for module '%(name)s'
"""
