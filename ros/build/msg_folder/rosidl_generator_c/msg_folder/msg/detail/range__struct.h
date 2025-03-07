// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from msg_folder:msg/Range.idl
// generated code does not contain a copyright notice

#ifndef MSG_FOLDER__MSG__DETAIL__RANGE__STRUCT_H_
#define MSG_FOLDER__MSG__DETAIL__RANGE__STRUCT_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>


// Constants defined in the message

// Include directives for member types
// Member 'from_id'
// Member 'to_id'
#include "rosidl_runtime_c/string.h"

/// Struct defined in msg/Range in the package msg_folder.
typedef struct msg_folder__msg__Range
{
  double range;
  double power;
  rosidl_runtime_c__String from_id;
  rosidl_runtime_c__String to_id;
} msg_folder__msg__Range;

// Struct for a sequence of msg_folder__msg__Range.
typedef struct msg_folder__msg__Range__Sequence
{
  msg_folder__msg__Range * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} msg_folder__msg__Range__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // MSG_FOLDER__MSG__DETAIL__RANGE__STRUCT_H_
