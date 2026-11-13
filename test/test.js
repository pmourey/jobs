import EditorJS from '@editorjs/editorjs';
import Header from '@editorjs/header';
import List from '@editorjs/list';

const editor = new EditorJS({
  /**
   * Id of Element that should contain the Editor
   */
  holder: 'editorjs',

  /**
   * Available Tools list.
   * Pass Tool's class or Settings object for each Tool you want to use
   */
  tools: {
    header: Header,
    list: List
  },
})

//var editor = new EditorJS();
//
//try {
//  await editor.isReady;
//  console.log('Editor.js is ready to work!')
//  /** Do anything you need after editor initialization */
//} catch (reason) {
//  console.log(`Editor.js initialization failed because of ${reason}`)
//}