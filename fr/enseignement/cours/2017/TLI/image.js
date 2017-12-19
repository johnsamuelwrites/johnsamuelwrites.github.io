function image() {
  var id = document.getElementById("image");
  var context = id.getContext("2d");
  var img = new Image();
  img.src = "rose.bmp";
  context.drawImage(img, 0, 0, 400, 600);
}

function imageRotate() {
  var id = document.getElementById("imageRotate");
  var context = id.getContext("2d");
  var img = new Image();
  img.src = "rose.bmp";
  context.rotate(10*Math.PI/180);
  context.drawImage(img, 200, 0, 400, 600);
}

function imageScale() {
  var id = document.getElementById("imageScale");
  var context = id.getContext("2d");
  var img = new Image();
  img.src = "rose.bmp";
  context.scale(0.5, 0.5);
  context.drawImage(img, 200, 0, 400, 600);
}

function imageData() {
  var id = document.getElementById("imageData");
  var context = id.getContext("2d");
  var img = new Image();
  img.src = "rose.bmp";
  context.drawImage(img, 200, 0, 400, 600);

  var data = context.getImageData(300,300,150,150);
  console.log(data);
  for(i=0; i< data.data.length; i+=4)
    if(data.data[i]<255 && data.data[i]>190) {
      data.data[i]=205;
      data.data[i+1]=205;
      data.data[i+2]=205;
      data.data[i+3]=205;
    }
  context.putImageData(data, 300,300);
}


image();
imageRotate();
imageScale();
imageData();
