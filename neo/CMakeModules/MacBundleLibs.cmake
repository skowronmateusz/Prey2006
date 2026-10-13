# macOS: make the built binaries use the libraries in the app bundle.
#
# The app bundle (Prey2006.app) ships SDL2/OpenAL in Contents/Frameworks, but the linker
# stores the absolute paths of the libraries found at build time (e.g. from Homebrew).
# After linking, every dependency that isn't part of the system is changed to
# @rpath/<library name>, and these rpaths are added:
#   @executable_path/../Frameworks  - the app bundle
#   <original library directories>  - so the binary still runs from output/macosx
# The game dylib is dlopen()ed by the executable and uses its rpaths.

set(_MAC_BUNDLE_LIBS_SCRIPT "${CMAKE_CURRENT_LIST_DIR}/MacBundleLibsRelink.cmake")

function(macos_bundle_relink _target)
	if(NOT APPLE)
		return()
	endif()

	get_target_property(_type ${_target} TYPE)
	if(_type STREQUAL "EXECUTABLE")
		set(_add_rpaths ON)
	else()
		set(_add_rpaths OFF)
	endif()

	add_custom_command(TARGET ${_target} POST_BUILD
		COMMAND "${CMAKE_COMMAND}"
			"-DFILE=$<TARGET_FILE:${_target}>"
			"-DADD_RPATHS=${_add_rpaths}"
			-P "${_MAC_BUNDLE_LIBS_SCRIPT}"
		COMMENT "Relinking ${_target} against @rpath for the app bundle"
		VERBATIM)
endfunction()
