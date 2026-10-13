# Run with: cmake -DFILE=<binary> -DADD_RPATHS=ON|OFF -P MacBundleLibsRelink.cmake
# see MacBundleLibs.cmake

execute_process(COMMAND otool -L "${FILE}"
	OUTPUT_VARIABLE _deps RESULT_VARIABLE _res)
if(NOT _res EQUAL 0)
	message(FATAL_ERROR "otool -L failed for ${FILE}")
endif()

get_filename_component(_file_name "${FILE}" NAME)
string(REPLACE "\n" ";" _deps "${_deps}")

set(_args)
set(_lib_dirs)
foreach(_line IN LISTS _deps)
	# lines look like "	/opt/homebrew/opt/sdl2-compat/lib/libSDL2-2.0.0.dylib (compatibility version ...)"
	if(NOT _line MATCHES "^[ \t]+([^ \t].*) \\(compatibility version")
		continue()
	endif()
	set(_dep "${CMAKE_MATCH_1}")
	# keep system libraries and paths that are already relative
	if(_dep MATCHES "^(/usr/lib/|/System/|@)")
		continue()
	endif()
	get_filename_component(_dep_name "${_dep}" NAME)
	get_filename_component(_dep_dir "${_dep}" DIRECTORY)
	list(APPEND _args -change "${_dep}" "@rpath/${_dep_name}")
	list(APPEND _lib_dirs "${_dep_dir}")
endforeach()

if(ADD_RPATHS)
	execute_process(COMMAND otool -l "${FILE}" OUTPUT_VARIABLE _load_cmds)
	list(REMOVE_DUPLICATES _lib_dirs)
	foreach(_rpath "@executable_path/../Frameworks" ${_lib_dirs})
		string(FIND "${_load_cmds}" "path ${_rpath} (offset" _found)
		if(_found EQUAL -1)
			list(APPEND _args -add_rpath "${_rpath}")
		endif()
	endforeach()
endif()

if(NOT _args)
	return()
endif()

execute_process(COMMAND install_name_tool ${_args} "${FILE}"
	RESULT_VARIABLE _res ERROR_VARIABLE _err)
if(NOT _res EQUAL 0)
	message(FATAL_ERROR "install_name_tool failed for ${FILE}: ${_err}")
endif()

# install_name_tool invalidates the signature, arm64 binaries must be signed to run
execute_process(COMMAND codesign --force -s - "${FILE}"
	RESULT_VARIABLE _res ERROR_VARIABLE _err)
if(NOT _res EQUAL 0)
	message(FATAL_ERROR "codesign failed for ${FILE}: ${_err}")
endif()

message(STATUS "Relinked ${_file_name} against @rpath")
